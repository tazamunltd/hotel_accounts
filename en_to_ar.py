from deep_translator import GoogleTranslator
import polib
import re

# Function to replace English numbers with Arabic-Indic numerals
def convert_to_arabic_numerals(text):
    arabic_numerals = {
        '0': '٠', '1': '١', '2': '٢', '3': '٣', '4': '٤',
        '5': '٥', '6': '٦', '7': '٧', '8': '٨', '9': '٩'
    }
    return ''.join(arabic_numerals.get(char, char) for char in text)

try:
    # Load the .po file
    po_file_path = r'E:\\Neo-Moment Projects\\Odoo_17\\tazamun_iinternal_v4\\test3.po'
    print(po_file_path)
    translated_file_path = r'E:\\Neo-Moment Projects\\Odoo_17\\tazamun_iinternal_v4\\test_ar3.po'

    po = polib.pofile(po_file_path)

    # Translate entries
    for entry in po:
        if not entry.msgstr:  # Only translate if msgstr is empty
            # Translate text
            translated_text = GoogleTranslator(source='en', target='ar').translate(entry.msgid)
            # Convert numbers in the translation to Arabic-Indic numerals
            translated_text_with_arabic_numerals = re.sub(r'\d', lambda x: convert_to_arabic_numerals(x.group()), translated_text)
            print(translated_text_with_arabic_numerals)
            entry.msgstr = translated_text_with_arabic_numerals

    # Save the translated .po file
    po.save(translated_file_path)
    print(f"Translation completed successfully! Translated file saved at: {translated_file_path}")

except OSError as e:
    print(f"Error processing PO file: {e}")
