# Welcome to Sonic Pi

samples_rain = ""
slow_rain = "C:/Users/lima/Desktop/samples_of_rain/slow-rain.wav"
thunder = "C:/Users/lima/Desktop/samples_of_rain/thunder-rain.wav"
gun = "C:/Users/lima/Desktop/samples_of_rain/big-gun-shot_B_minor.wav"
heavey_rain =  "C:/Users/lima/Desktop/samples_of_rain/rain-texture-sound-fx-loop_115bpm_E_minor"
live_loop :rain1 do
  sample slow_rain, attack: 5, release: 5, amp: 1.2
  sleep 25
end

live_loop :thunder_sound do
  sample thunder, attack: 20, release: 20, amp: rrand(0.5, 1), rate: 0.9
  sleep 60
end

live_loop :rain2 do
  sample heavey_rain, amp:0.3, attack: 3, release: 4
  sleep 16
end


#live_loop :gun_sound do
#  sleep 60
#  sample gun, rate: 1, amp: 1, attack: 1, release: 2
#  sleep rrand(30, 120)
#end


