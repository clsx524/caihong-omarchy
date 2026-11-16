-- Caihong's touchscreen and pen belong to the internal panel, not the
-- combined desktop when an external display is attached. Hyprland handles
-- the panel's current scale/transform; the Plasma-only KWin calibration
-- service must not be started here. Do not change the working pogo keyboard.
-- @OUTPUT@ is replaced with the live internal connector by setup-user.
hl.config({
  input = {
    touchdevice = { output = "@OUTPUT@" },
    tablet = { output = "@OUTPUT@" },
  },
})
