import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

def generate_sitemap(base_url="https://policycrab.tech", output_path="frontend/public/sitemap.xml"):
    # Define the core public pages
    pages = [
        {"loc": "", "priority": "1.0", "changefreq": "weekly"},
        {"loc": "/policy", "priority": "0.9", "changefreq": "monthly"},
        {"loc": "/claim", "priority": "0.9", "changefreq": "monthly"},
        {"loc": "/chat", "priority": "0.8", "changefreq": "monthly"},
        {"loc": "/benchmarks", "priority": "0.8", "changefreq": "monthly"},
        {"loc": "/resources", "priority": "0.9", "changefreq": "weekly"},
        {"loc": "/auth", "priority": "0.5", "changefreq": "monthly"},
    ]

    # Create root element
    urlset = ET.Element("urlset")
    urlset.set("xmlns", "http://www.sitemaps.org/schemas/sitemap/0.9")

    # Add URLs
    for page in pages:
        url_el = ET.SubElement(urlset, "url")
        loc = ET.SubElement(url_el, "loc")
        loc.text = f"{base_url}{page['loc']}"
        
        lastmod = ET.SubElement(url_el, "lastmod")
        lastmod.text = datetime.now().strftime("%Y-%m-%d")
        
        changefreq = ET.SubElement(url_el, "changefreq")
        changefreq.text = page["changefreq"]
        
        priority = ET.SubElement(url_el, "priority")
        priority.text = page["priority"]

    # Write to file
    tree = ET.ElementTree(urlset)
    ET.indent(tree, space="  ", level=0)
    
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    tree.write(out_file, encoding="utf-8", xml_declaration=True)
    
    print(f"Generated {output_path} with {len(pages)} URLs.")

if __name__ == "__main__":
    generate_sitemap()
