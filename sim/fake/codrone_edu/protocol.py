from enum import Enum


class Note(Enum):
    # same numbering as the real library: C1 = 0, one step per semitone
    C1 = 0; CS1 = 1; D1 = 2; DS1 = 3; E1 = 4; F1 = 5; FS1 = 6; G1 = 7; GS1 = 8; A1 = 9; AS1 = 10; B1 = 11
    C2 = 12; CS2 = 13; D2 = 14; DS2 = 15; E2 = 16; F2 = 17; FS2 = 18; G2 = 19; GS2 = 20; A2 = 21; AS2 = 22; B2 = 23
    C3 = 24; CS3 = 25; D3 = 26; DS3 = 27; E3 = 28; F3 = 29; FS3 = 30; G3 = 31; GS3 = 32; A3 = 33; AS3 = 34; B3 = 35
    C4 = 36; CS4 = 37; D4 = 38; DS4 = 39; E4 = 40; F4 = 41; FS4 = 42; G4 = 43; GS4 = 44; A4 = 45; AS4 = 46; B4 = 47
    C5 = 48; CS5 = 49; D5 = 50; DS5 = 51; E5 = 52; F5 = 53; FS5 = 54; G5 = 55; GS5 = 56; A5 = 57; AS5 = 58; B5 = 59
    C6 = 60; CS6 = 61; D6 = 62; DS6 = 63; E6 = 64; F6 = 65; FS6 = 66; G6 = 67; GS6 = 68; A6 = 69; AS6 = 70; B6 = 71
    C7 = 72; CS7 = 73; D7 = 74; DS7 = 75; E7 = 76; F7 = 77; FS7 = 78; G7 = 79; GS7 = 80; A7 = 81; AS7 = 82; B7 = 83
    C8 = 84; CS8 = 85; D8 = 86; DS8 = 87; E8 = 88; F8 = 89; FS8 = 90; G8 = 91; GS8 = 92; A8 = 93; AS8 = 94; B8 = 95
    Mute = 0xEE
    Fin = 0xFF
