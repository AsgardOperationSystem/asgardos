-- AUD-3: every output plays at Asgard's one volume (audio.volume), not the level WirePlumber saved for it.
--
-- WirePlumber keeps a level per output (route) and restores it whenever the output appears: Bluetooth headphones
-- connecting, the jack, a profile change, boot. Asgard has one volume, which the keys step from, so an output came
-- back at its own old level and the first key press jumped to audio.volume +/- 5 (Thor 2026-11-17: speaker saved at
-- 45 %, headphones at 90 %, audio.volume 45).
--
-- `volume` publishes the level (percent, as pactl takes it) as "asgard.volume" on the default metadata. This hook runs
-- after device/apply-route-props filled in the saved levels and puts that one on every output route instead. The last
-- level seen is kept in its own state file, for the outputs that appear before `volume` runs (boot, or a restart).

cutils = require ("common-utils")
devinfo = require ("device-info-cache")
log = Log.open_topic ("s-asgard-volume")

state = State ("asgard-volume")
state_table = state:load ()

-- pactl's percent is cubic: 45 % is 0.45^3 = 0.091 on the route.
function level ()
  local metadata = cutils.get_default_metadata_object ()
  local percent = metadata and tonumber (metadata:find (0, "asgard.volume"))
  if percent then
    if tostring (percent) ~= state_table ["percent"] then
      state_table ["percent"] = tostring (percent)
      state:save_after_timeout (state_table)
    end
  else
    percent = tonumber (state_table ["percent"])
  end
  if not percent then
    return nil
  end
  percent = math.max (0, math.min (100, percent))
  return (percent / 100) ^ 3
end

SimpleEventHook {
  name = "asgard/one-volume",
  after = "device/apply-route-props",
  before = "device/apply-routes",
  interests = {
    EventInterest {
      Constraint { "event.type", "=", "select-routes" },
    },
  },
  execute = function (event)
    local device = event:get_subject ()
    local selected_routes = event:get_data ("selected-routes")
    local dev_info = devinfo:get_device_info (device)
    local volume = level ()
    if not selected_routes or not dev_info or not volume then
      return
    end

    local new_selected_routes = {}
    for device_id, route in pairs (selected_routes) do
      route = Json.Raw (route):parse ()
      local route_info = devinfo.find_route_info (dev_info, route, false)
      local props = route.props or {}

      if route_info and route_info.direction == "Output" then
        local channels = props.channelVolumes and #props.channelVolumes or 0
        if channels == 0 then
          channels = props.channelMap and #props.channelMap or 0
        end
        props.channelVolumes = {}
        for i = 1, math.max (channels, 1) do
          props.channelVolumes [i] = volume
        end
        log:info (device, string.format ("route %s of %s at %.6f", route_info.name, dev_info.name, volume))
      end

      -- back to Json, as device/apply-route-props hands them on
      for _, key in ipairs ({ "channelVolumes", "channelMap", "iec958Codecs" }) do
        if props [key] then
          props [key] = Json.Array (props [key])
        end
      end
      route.props = Json.Object (props)
      new_selected_routes [device_id] = Json.Object (route):to_string ()
    end

    event:set_data ("selected-routes", new_selected_routes)
  end
}:register ()
