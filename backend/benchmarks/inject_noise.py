import os
import json
import random
import glob

def ocr_typo(text):
    """Introduce common OCR errors."""
    subs = {
        'O': '0', '0': 'O',
        'l': '1', '1': 'l', 'I': '1',
        'c': 'e', 'e': 'c',
        'rn': 'm', 'm': 'rn',
        'S': '5', '5': 'S'
    }
    chars = list(text)
    for i in range(len(chars)):
        if chars[i] in subs and random.random() < 0.05:  # 5% chance per char
            chars[i] = subs[chars[i]]
    return "".join(chars)

def drop_punctuation(text):
    """Randomly drop commas and periods to simulate run-on sentences."""
    chars = []
    for c in text:
        if c in {',', '.'} and random.random() < 0.4:
            continue
        chars.append(c)
    return "".join(chars)

def inject_artifacts(text):
    """Prepend or append messy fax/hospital artifacts."""
    prefixes = [
        "[FAX RCV 10:24 AM PAGE 2/4]\n",
        "*** CONFIDENTIAL PATIENT RECORD ***\n",
        "Scanned Document (low quality):\n",
        "NOTES: ",
        "[ILLEGIBLE...]\n"
    ]
    suffixes = [
        "\n[END OF PAGE]",
        "\n--- dictation transcribed by auto-svc ---",
        " ?? [verify code]"
    ]
    
    if random.random() < 0.3:
        text = random.choice(prefixes) + text
    if random.random() < 0.3:
        text = text + random.choice(suffixes)
    return text

def random_casing(text):
    """Randomly UPPERCASE segments or the whole thing."""
    if random.random() < 0.15:
        return text.upper()
    return text

def inject_noise(text):
    if not text:
        return text
    text = ocr_typo(text)
    text = drop_punctuation(text)
    text = inject_artifacts(text)
    text = random_casing(text)
    return text

def process_cases():
    cases_dir = "cases"
    files = glob.glob(os.path.join(cases_dir, "*.json"))
    modified_count = 0
    for file_path in files:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        original_desc = data.get("claim_description", "")
        if original_desc:
            noisy_desc = inject_noise(original_desc)
            data["claim_description"] = noisy_desc
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            modified_count += 1
            
    print(f"Injected noise into {modified_count} files in {cases_dir}/.")

if __name__ == "__main__":
    process_cases()
