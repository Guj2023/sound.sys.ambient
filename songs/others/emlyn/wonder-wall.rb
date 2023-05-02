# Wonderwall - Oasis

# Strum a chord with a certain delay between strings
define :guitar_strum do |chrd, dt|
    in_thread do
      play_pattern_timed chrd.to_a.drop_while{|n| [nil,:r].include? n}, dt
    end
  end
  
  define :strum do |chrd, pattern=nil, t=0.25, dt=0.025|
    if pattern == nil then
      guitar_strum(chrd, dt)
    else
      pattern.split(//).each do |shape|
        case shape
        when 'D'
          guitar_strum chrd, dt
        when 'd'
          with_fx :level, amp: 0.7 do
            guitar_strum chrd, dt
          end
        when 'U'
          with_fx :level, amp: 0.8 do
            guitar_strum chrd.reverse, dt*0.9
          end
        when 'u'
          with_fx :level, amp: 0.6 do
            guitar_strum chrd.reverse, dt*0.9
          end
        else
          # nothing
        end
        sleep t
      end
    end
  end
  
  define :pl do |notes, sus=0.5, rel=nil|
    rel ||= 1 - sus
    notes.each_slice(2) do |n,d|
      if d.respond_to?(:each) then # slur
        dtot = d.reduce(:+)
        synth = play n[0], sustain: sus * dtot, release: rel * dtot
        sleep d[0]
        d[1..-1].zip(n[1..-1]).each do |dd, nn|
          control synth, note: nn
          sleep dd
        end
      else
        play n, sustain: sus * d, release: rel * d
        sleep d
      end
    end
  end
  
  class LyricStrx < String
    def initialize(s)
      super s
    end
    # Override inspect to return the string as-is (without adding quotes)
    def inspect
      to_s
    end
  end
  
  define :lyrics do |str|
    puts LyricStrx.new(str)
  end
  
  use_debug false
  use_bpm 68
  
  with_fx :reverb, room: 0.9 do
    
    at 16 do
      use_synth :fm
      use_synth_defaults attack: 0.05, slide: 0.025, depth: 1.5
      with_fx :distortion, amp: 0.5 do
        lyrics "Today is gonna be the day that they're"
        pl [:r, 0.5, :B4, 0.5, :A4, 0.75, :G4, 0.25, [:A4, :G4], [0.25, 0.25], :A4, 0.25, :G4, 0.25, :A4, 0.5, :A4, 0.25, :G4, 0.25]
        lyrics "gonna throw it back to you."
        pl [[:A4, :G4], [0.25, 0.25], :A4, 0.25, :G4, 0.25, :A4, 0.5, :B4, 0.25, :G4, 1.25, :r, 1]
        lyrics "By now you should've some how"
        pl [:r, 0.5, :B4, 0.5, :A4, 0.75, :G4, 0.25, :A4, 0.25, :G4, 0.25, :A4, 0.5, :A4, 0.5]
        lyrics "realised what you gotta do."
        pl [[:A4, :G4], [0.25, 0.25], :A4, 0.5, :A4, 0.25, :G4, 0.25, [:A4, :B4], [0.5, 0.25], :G4, 1.5, :r, 1]
        lyrics "I don't believe that anybody"
        pl [:B4, 0.25, :D5, 0.25, [:B4, :D5], [0.25, 0.75], :D5, 0.25, :E5, 0.75, :D5, 0.25, :A4, 0.5, :G4, 0.75]
        lyrics "feels the way I do"
        pl [:A4, 0.75, :A4, 0.25, [:A4, :B4], [0.25, 0.5], :G4, 1]
        lyrics "about you now"
        pl [:E4, 0.25, :E4, 0.5, :E4, 0.25, [:G4, :E4], [0.5, 1.75], :r, 5.5]
      end
    end
    
    use_synth :pluck
    use_synth_defaults coef: 0.35
    
    with_fx :lpf, cutoff: 110 do
      em7   = [40, 47, 52, 55, 62, 67]
      g     = [43, 47, 50, 55, 62, 67]
      dsus4 = [:r, :r, 50, 57, 62, 67]
      a7sus4= [:r, 45, 52, 55, 62, 67]
      5.times do
        strum em7,    'D.d.D.dU'
        strum g,      'dUD.D.du'
        strum dsus4,  'DUD.D.d'
        strum a7sus4, 'U.U.uduDu'
      end
      strum em7,    'D.d.D.dU'
      strum g,      'dUD.D.du'
      strum dsus4,  'DUD.D.d'
      strum a7sus4, 'U.U.uduD.'
    end
  end