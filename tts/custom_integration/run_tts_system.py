#!/usr/bin/env python3
"""
IndexTTS2 Forum Integration System - Main Entry Point

This script starts the TTS forum integration system.
"""

import sys
import os

# Add the current directory to the path so we can import the tts module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == '__main__':
    from integration.start_tts_system import main
    main()
