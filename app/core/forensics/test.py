from app.core.forensics.digital_tampering import detect_digital_tempering
from app.core.forensics.physical_tampering import detect_physical_tempering
from app.core.forensics.aadhaar_qr_verifier import verify_aadhaar_qr
# result = detect_digital_tempering("app/core/forensics/duplicate.jpeg")
result = detect_digital_tempering("app/core/forensics/duplicate.jpeg")

# ocr_details =  {
#       "full_name": "Patel Dhwanit Pareshkumar",
#       "dob": "10-10-2005",
#       "gender": "Male",
#       "doc_number": "496915037988"
#   }
# result = verify_aadhaar_qr("app/core/forensics/aadhar.jpeg", ocr_details)

print(result)