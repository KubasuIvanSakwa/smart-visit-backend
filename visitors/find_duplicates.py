import os
import re

def find_definitions():
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'def KioskCheckInView(' in content:
                        print(f"Function found in: {path}")
                    if 'class KioskCheckInView(' in content:
                        print(f"Class found in: {path}")

find_definitions()