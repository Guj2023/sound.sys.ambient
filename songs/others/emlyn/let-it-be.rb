# Let it be - The Beatles (guitar)
# Uses the guitar helper
define :guitar do |tonic, name=nil, tuning=:guitar, debug=false|
    tunings = {
      :ukulele => [:g, :c, :e, :a],
      :guitar => [:e2, :a2, :d3, :g3, :b3, :e4]
    }
    tuning = tunings[tuning] || tuning
    
    # Next note higher or equal to base note n, that is in the chord c
    define :next_note do |n, c|
      # Make sure n is a number
      n = note(n)
      # Get distances to each note in chord, add smallest to base note
      n + (c.map {|x| (note(x) - n) % 12}).min
    end
    
    if tonic.respond_to?(:each) and name==nil then
      chrd = tonic
    else
      chrd = (chord tonic, name || :M)
    end
    
    # For each string, get the next higher note that is in the chord
    c = tuning.map {|n| next_note(n, chrd)}
    
    # We want the lowest note to be the root of the chord
    root = note(chrd[0])
    first_root = c.take_while {|n| (n - root) % 12 != 0}.count
    
    # Drop up to half the lowest strings to make that the case if possible
    if first_root > 0 and first_root < tuning.count / 2
      c = (ring :r) * first_root + c.drop(first_root)
    end
    
    # Display chord fingering
    if debug
      puts c.zip(tuning).map {|n, s| if n == :r then 'x' else (n - note(s)) end}.to_a.join, c
    end
    c
  end
  
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
  
  use_bpm 72
  use_synth :pluck
  
  with_fx :reverb, room: 1 do
    with_fx :lpf, cutoff: 95 do
      2.times do
        strum guitar(:c), 'D.du', 0.5
        strum guitar(:g), 'D.du', 0.5
        strum guitar(:a, :m), 'D.', 0.5
        strum guitar(:a, :m7), 'du', 0.5
        strum guitar(:f), 'D.du', 0.5
        strum guitar(:c), 'D.du', 0.5
        strum guitar(:g), 'D.du', 0.5
        strum guitar(:f), 'D.', 0.5
        strum [:e3, :g3], 'd', 0.5
        strum [:d3, :g3], 'd', 0.5
        strum guitar(:c), 'D...', 0.5
      end
    end
  end
  