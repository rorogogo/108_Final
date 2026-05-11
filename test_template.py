from jinja2 import Environment, FileSystemLoader
import json

env = Environment(loader=FileSystemLoader('templates'))
tmpl = env.get_template('weapons.html')

# Test data
with open("data/weapons.json") as f:
    weapons = json.load(f)

test_vars = {
    "weapons": weapons,
    "owned": {k: True for k in list(weapons.keys())[:5]},
    "owned_count": 5,
    "user": None,
    "profile_pic": "",
    "is_logged_in": False
}

# Render template
try:
    output = tmpl.render(test_vars)
    print("Template rendered successfully")
    
    # Find the script section
    script_start = output.find('<script>')
    script_end = output.find('</script>', script_start)
    script = output[script_start:script_end+9]
    
    # Show first 30 lines
    lines = script.split('\n')
    for i, line in enumerate(lines[:30]):
        print(f"{i}: {line[:120]}")
except Exception as e:
    print(f"Template rendering error: {e}")

