from datetime import datetime


# ---------------------------------------------------------
# MRZ CHECK DIGIT
# ---------------------------------------------------------

def mrz_char_value(char: str) -> int:
    """
    ICAO MRZ character values:
        0-9 -> 0-9
        A-Z -> 10-35
        <   -> 0
    """
    if char == "<":
        return 0

    if char.isdigit():
        return int(char)

    if "A" <= char <= "Z":
        return ord(char) - ord("A") + 10

    raise ValueError(f"Invalid MRZ character: {char}")


def calculate_check_digit(value: str) -> str:
    """
    ICAO MRZ check digit algorithm.

    Weights repeat:
        7, 3, 1
    """

    weights = [7, 3, 1]

    total = 0

    for i, char in enumerate(value):
        total += mrz_char_value(char) * weights[i % 3]

    return str(total % 10)


def validate_check_digit(value: str, check_digit: str) -> bool:
    """
    Check whether the supplied check digit is correct.
    """
    if not value or not check_digit:
        return False

    return calculate_check_digit(value) == check_digit


def parse_td3_mrz(mrz: str):
    """
    Parse a standard TD3 passport MRZ.

    Returns:
        dict containing parsed fields
    """

    # Remove spaces/newlines
    mrz = mrz.upper().replace(" ", "").replace("\n", "")

    if len(mrz) != 88:
        return {
            "valid": False,
            "error": f"Invalid MRZ length: {len(mrz)}. Expected 88 characters."
        }

    line1 = mrz[:44]
    line2 = mrz[44:88]

    # -----------------------------------------------------
    # LINE 1
    # -----------------------------------------------------

    document_type = line1[0]
    issuing_country = line1[2:5]

    name_section = line1[5:44]

    # Format:
    # SURNAME<<GIVEN<NAMES<<<<<<<<
    parts = name_section.split("<<", 1)

    surname = parts[0].replace("<", " ").strip()

    if len(parts) > 1:
        given_names = parts[1].replace("<", " ").strip()
    else:
        given_names = ""

    # -----------------------------------------------------
    # LINE 2
    # -----------------------------------------------------

    passport_number = line2[0:9]
    passport_number_check = line2[9]

    nationality = line2[10:13]

    dob = line2[13:19]
    dob_check = line2[19]

    sex = line2[20]

    expiry_date = line2[21:27]
    expiry_check = line2[27]

    optional_data = line2[28:42]

    optional_data_check = line2[42]

    composite_check = line2[43]

    return {
        "valid": True,

        "document_type": document_type,
        "issuing_country": issuing_country,

        "surname": surname,
        "given_names": given_names,

        "passport_number": passport_number.replace("<", ""),

        "nationality": nationality,

        "dob": dob,
        "sex": sex,

        "expiry_date": expiry_date,

        "optional_data": optional_data,

        # Keep these for validation
        "_raw": mrz,
        "_line1": line1,
        "_line2": line2,

        "_checks": {
            "passport_number": passport_number_check,
            "dob": dob_check,
            "expiry_date": expiry_check,
            "optional_data": optional_data_check,
            "composite": composite_check
        }
    }


def validate_mrz_check_digits(parsed):
    """
    Validate all TD3 MRZ check digits.
    """

    line2 = parsed["_line2"]

    passport_number = line2[0:9]
    passport_check = line2[9]

    dob = line2[13:19]
    dob_check = line2[19]

    expiry = line2[21:27]
    expiry_check = line2[27]

    optional_data = line2[28:42]
    optional_check = line2[42]

    composite_check = line2[43]

    results = {}

    # Passport number
    results["passport_number"] = validate_check_digit(
        passport_number,
        passport_check
    )

    # DOB
    results["dob"] = validate_check_digit(
        dob,
        dob_check
    )

    # Expiry
    results["expiry_date"] = validate_check_digit(
        expiry,
        expiry_check
    )

    # Optional data
    results["optional_data"] = validate_check_digit(
        optional_data,
        optional_check
    )

    # Composite check
    #
    # TD3 composite data:
    # passport number + check digit
    # DOB + check digit
    # expiry + check digit
    # optional data + check digit
    #
    composite_data = (
        passport_number +
        passport_check +
        dob +
        dob_check +
        expiry +
        expiry_check +
        optional_data +
        optional_check
    )

    results["composite"] = validate_check_digit(
        composite_data,
        composite_check
    )

    return results


def normalize_text(value):
    if value is None:
        return ""

    return (
        str(value)
        .upper()
        .replace("<", " ")
        .strip()
    )


def normalize_name(value):
    value = normalize_text(value)

    return " ".join(value.split())


def normalize_date(value):
    """
    Convert common date formats into YYYY-MM-DD.
    """

    if value is None:
        return None

    value = str(value).strip()

    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%d.%m.%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass

    return None


def parse_mrz_date(value: str):
    try:
        year = int(value[0:2])
        month = int(value[2:4])
        day = int(value[4:6])

        # MRZ uses two digit years.
        # Standard practical interpretation:
        # 00-49 -> 2000-2049
        # 50-99 -> 1950-1999

        if year <= 49:
            year += 2000
        else:
            year += 1900

        return datetime(year, month, day).date()

    except (ValueError, IndexError):
        return None


def names_match(document_name, surname, given_names):

    document_name = normalize_name(document_name)

    mrz_name = normalize_name(
        f"{given_names} {surname}"
    )

    if document_name == mrz_name:
        return True

    # Compare words instead of order
    doc_parts = set(document_name.split())
    mrz_parts = set(mrz_name.split())

    return doc_parts == mrz_parts

NATIONALITY_MAP = {
    "IND": ["IND", "INDIA", "INDIAN"],
    "USA": ["USA", "UNITED STATES", "AMERICAN"],
    "GBR": ["GBR", "UK", "UNITED KINGDOM", "BRITISH"],
}

def nationality_matches(document_nationality, mrz_nationality):

    document_nationality = normalize_text(
        document_nationality
    )

    mrz_nationality = normalize_text(
        mrz_nationality
    )

    allowed_values = NATIONALITY_MAP.get(
        mrz_nationality,
        [mrz_nationality]
    )

    return document_nationality in allowed_values

def verify_document_mrz(document):
    """
    Verify the MRZ stored in a Document against the
    document's extracted visible fields.

    Returns:
        {
            "valid": bool,
            "reasons": [],
            "checks": {}
        }
    """

    reasons = []

    # -----------------------------------------------------
    # 1. Check MRZ exists
    # -----------------------------------------------------

    if not document.mrz_no:
        return {
            "valid": False,
            "reasons": ["MRZ is missing"],
            "checks": {}
        }

    # -----------------------------------------------------
    # 2. Parse MRZ
    # -----------------------------------------------------

    parsed = parse_td3_mrz(document.mrz_no)

    if not parsed["valid"]:
        return {
            "valid": False,
            "reasons": [parsed["error"]],
            "checks": {}
        }

    # -----------------------------------------------------
    # 3. Validate check digits
    # -----------------------------------------------------

    check_results = validate_mrz_check_digits(parsed)

    for field, valid in check_results.items():

        if not valid:
            reasons.append(
                f"MRZ {field} check digit is invalid"
            )

    # -----------------------------------------------------
    # 4. Passport number
    # -----------------------------------------------------

    mrz_passport_number = normalize_text(
        parsed["passport_number"]
    )

    document_passport_number = normalize_text(
        document.doc_number
    )

    if mrz_passport_number != document_passport_number:

        reasons.append(
            f"Passport number mismatch: "
            f"document={document.doc_number}, "
            f"MRZ={parsed['passport_number']}"
        )

    # -----------------------------------------------------
    # 5. Name
    # -----------------------------------------------------

    if document.full_name:

        if not names_match(
            document.full_name,
            parsed["surname"],
            parsed["given_names"]
        ):

            reasons.append(
                f"Name mismatch: "
                f"document={document.full_name}, "
                f"MRZ={parsed['given_names']} {parsed['surname']}"
            )

    # -----------------------------------------------------
    # 6. DOB
    # -----------------------------------------------------

    document_dob = normalize_date(document.dob)
    mrz_dob = parse_mrz_date(parsed["dob"])

    if document_dob and mrz_dob:

        if document_dob != mrz_dob:

            reasons.append(
                f"Date of birth mismatch: "
                f"document={document_dob}, "
                f"MRZ={mrz_dob}"
            )

    # -----------------------------------------------------
    # 7. Gender
    # -----------------------------------------------------

    if document.gender:

        document_gender = normalize_text(document.gender)
        mrz_gender = normalize_text(parsed["sex"])

        gender_map = {
            "MALE": "M",
            "M": "M",
            "FEMALE": "F",
            "F": "F",
            "X": "X"
        }

        document_gender = gender_map.get(
            document_gender,
            document_gender
        )

        if document_gender != mrz_gender:

            reasons.append(
                f"Gender mismatch: "
                f"document={document.gender}, "
                f"MRZ={parsed['sex']}"
            )

    # -----------------------------------------------------
    # 8. Expiry date
    # -----------------------------------------------------

    document_expiry = normalize_date(
        document.expiry_date
    )

    mrz_expiry = parse_mrz_date(
        parsed["expiry_date"]
    )

    if document_expiry and mrz_expiry:

        if document_expiry != mrz_expiry:

            reasons.append(
                f"Expiry date mismatch: "
                f"document={document_expiry}, "
                f"MRZ={mrz_expiry}"
            )

    # -----------------------------------------------------
    # 9. Nationality
    # -----------------------------------------------------

    if document.nationality:

        if not nationality_matches(
            document.nationality,
            parsed["nationality"]
        ):

            reasons.append(
                f"Nationality mismatch: "
                f"document={document.nationality}, "
                f"MRZ={parsed['nationality']}"
            )

    # -----------------------------------------------------
    # FINAL RESULT
    # -----------------------------------------------------

    return {
        "valid": len(reasons) == 0,
        "reasons": reasons,

        "checks": {
            "mrz_format": True,

            "check_digits": check_results,

            "fields": {
                "passport_number": (
                    mrz_passport_number ==
                    document_passport_number
                ),

                "name": names_match(
                    document.full_name or "",
                    parsed["surname"],
                    parsed["given_names"]
                ),

                "dob": (
                    not document_dob or
                    not mrz_dob or
                    document_dob == mrz_dob
                ),

                "gender": (
                    not document.gender or
                    document_gender == mrz_gender
                ),

                "expiry_date": (
                    not document_expiry or
                    not mrz_expiry or
                    document_expiry == mrz_expiry
                ),

                "nationality": (
                    not document.nationality or
                    nationality_matches(
                        document.nationality,
                        parsed["nationality"]
                    )
                )
            }
        },

        "mrz_data": {
            "surname": parsed["surname"],
            "given_names": parsed["given_names"],
            "passport_number": parsed["passport_number"],
            "nationality": parsed["nationality"],
            "dob": mrz_dob,
            "sex": parsed["sex"],
            "expiry_date": mrz_expiry
        }
    }