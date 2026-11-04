import glob

LINK = '''<link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">'''
TAG = '''<script src="{{ url_for('static', filename='theme.js') }}"></script>'''

for path in sorted(glob.glob("templates/*.html")):
    with open(path, encoding="utf-8") as f:
        html = f.read()
    if "theme.js" in html:
        print("OK      ", path, "already has the theme script")
    elif LINK in html:
        with open(path, "w", encoding="utf-8") as f:
            f.write(html.replace(LINK, LINK + "\n    " + TAG, 1))
        print("FIXED   ", path)
    else:
        print("MANUAL  ", path, "- add this line inside <head>:", TAG)