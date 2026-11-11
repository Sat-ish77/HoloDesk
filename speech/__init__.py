"""Speech in and out, built for a laptop with no GPU.

  wake word      stays on the small local Whisper (cheap, always on, private)
  the command    goes to a hosted Whisper large-v3, which is far better at
                 Nepali and mixed Nepali-English than anything a CPU can run
  Nepali speech  uses a neural Nepali voice (Windows SAPI has none)
"""
