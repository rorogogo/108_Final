import urllib.request
import re

response = urllib.request.urlopen('http://127.0.0.1:5000/weapons')
html = response.read().decode('utf-8')

# Find all script tags
scripts = re.findall(r'<script[^>]*>.*?</script>', html, re.DOTALL)

# Look at main script
main_script = scripts[2] if len(scripts) > 2 else ""
print(f"Main script length: {len(main_script)}")
print(f"Main script has 'weaponsData': {'weaponsData' in main_script}")

# Get all lines of main script
lines = main_script.split('\n')
print(f"Total lines in main script: {len(lines)}")

# Print first 20 and last 20 lines
print("\n=== FIRST 20 LINES ===")
for i, line in enumerate(lines[:20]):
    print(f"{i}: {line}")

print("\n=== LAST 20 LINES ===")
for i, line in enumerate(lines[-20:], start=len(lines)-20):
    print(f"{i}: {line}")

# Check line with const
const_lines = [i for i, l in enumerate(lines) if 'const ' in l]
print(f"\n=== Lines with 'const' ===")
for i in const_lines:
    print(f"{i}: {lines[i]}")



