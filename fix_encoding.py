"""Rewrite the tab names and title in 3_under_the_hood.py using safe Unicode escapes."""

path = "pages/3_under_the_hood.py"

with open(path, "r", encoding="utf-8", errors="replace") as f:
    content = f.read()

import re

# 1. Fix page_config icon
content = re.sub(
    r'page_icon=["\'][^"\']*["\']',
    'page_icon="\u2699\ufe0f"',
    content
)

# 2. Fix all tab names (replace the entire st.tabs(...) call)
content = re.sub(
    r'tab1, tab2, tab3, tab4\s*=\s*st\.tabs\(\[.*?\]\)',
    'tab1, tab2, tab3, tab4 = st.tabs([\n'
    '    "\U0001f3af Live Bidding Arena",\n'
    '    "\U0001f9fe Auction Ledger",\n'
    '    "\U0001f50d Node Deep Scan",\n'
    '    "\U0001f4ca Fleet Statistics"\n'
    '])',
    content,
    flags=re.DOTALL
)

# 3. Fix st.title
content = re.sub(
    r'st\.title\(["\'][^"\']*["\'\)]*\)',
    'st.title("\u2699\ufe0f Swarm Intelligence Forensics")',
    content,
    count=1
)

# 4. Fix sub-section headers that are corrupted 
# "### 🎯 Live Bidding Arena"  
content = re.sub(
    r'### [^\n"]*Live Bidding Arena',
    '### \U0001f3af Live Bidding Arena',
    content
)
# "### 🔍 Node Deep Scan..."
content = re.sub(
    r'### [^\n"]*Node Deep Scan[^\n"]*',
    '### \U0001f50d Node Deep Scan \u2014 Full Telemetry Vector',
    content
)

# 5. Remove any remaining replacement chars
content = content.replace('\ufffd', '')

# 6. Remove the \x8f continuation byte artifact (shows as empty glyphs)
content = re.sub(r'[\x8f\x8d\x9f]', '', content)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Fixed. Checking key strings:")
for pattern in ['page_icon', 'st.title', 'st.tabs', 'Live Bidding', 'Node Deep Scan']:
    idx = content.find(pattern)
    if idx >= 0:
        print(f"  {pattern}: {repr(content[idx:idx+60])}")
