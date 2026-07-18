import fitz # PyMuPDF
import sys
import uuid

doc = fitz.open()

# Generate 150 pages
for i in range(1, 151):
    page = doc.new_page(width=595, height=842) # A4
    text = f"--- Page {i} ---\n\n"
    text += "THIS IS A TEST POLICY DOCUMENT.\n\n"
    if i == 42:
        text += "CRITICAL CLAUSE: The patient's exact policy requires a prior authorization waiver in the event of an emergency appendectomy.\n"
    elif i == 100:
        text += "CRITICAL EXCLUSION: Out-of-network cosmetic surgery is explicitly NOT covered under any circumstances.\n"
    elif i == 149:
        text += "APPEAL DEADLINE: You have exactly 180 days to appeal any denial from the date of the Explanation of Benefits.\n"
    else:
        text += "Standard insurance boilerplate text. Coverage depends on medical necessity. " * 50
    page.insert_text(fitz.Point(50, 50), text, fontsize=11)

doc.save("test_policy_150.pdf")
print("Generated test_policy_150.pdf")
