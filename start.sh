#!/bin/bash

# Przejdź do katalogu projektu
cd /home/kostyk/gitrepos/Garage-Parking-Assistant

# Usuń plik background_frame.jpg, jeśli istnieje
rm -f background_frame.jpg

# Aktywuj środowisko wirtualne i uruchom projekt
sudo -E /home/kostyk/gitrepos/Garage-Parking-Assistant/.venv/bin/python3 src/garage_parking_assistant/main.py
