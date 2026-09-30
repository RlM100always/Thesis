"""Versioned Bangladesh reference records from authoritative public sources.

These are reference choices, not invented demo transactions.  Keeping the
source and verification date beside every row makes later refreshes auditable.
"""

from datetime import date

DISTRICT_SOURCE = "https://gis.dghs.gov.bd/server/rest/services/Hosted/bgd_admbnda_adm2_bbs_20201113/FeatureServer/0"
NAME_SOURCE = "https://bangladesh.gov.bd/views/district-list/"
MFS_SOURCE = "https://www.bb.org.bd/en/index.php/financialsystems/paysystems"
VERIFIED_ON = date(2026, 9, 30)

DIVISIONS = [
    ("barishal", "Barishal", "বরিশাল"), ("chattogram", "Chattogram", "চট্টগ্রাম"),
    ("dhaka", "Dhaka", "ঢাকা"), ("khulna", "Khulna", "খুলনা"),
    ("mymensingh", "Mymensingh", "ময়মনসিংহ"), ("rajshahi", "Rajshahi", "রাজশাহী"),
    ("rangpur", "Rangpur", "রংপুর"), ("sylhet", "Sylhet", "সিলেট"),
]

# BBS/DGHS pcode, canonical English label, National Portal Bangla label,
# parent division code. Historical English spellings in the GIS layer are
# normalized for display while the official pcode remains unchanged.
DISTRICTS = [
    ("BD1004", "Barguna", "বরগুনা", "barishal"), ("BD1006", "Barishal", "বরিশাল", "barishal"),
    ("BD1009", "Bhola", "ভোলা", "barishal"), ("BD1042", "Jhalokathi", "ঝালকাঠি", "barishal"),
    ("BD1078", "Patuakhali", "পটুয়াখালী", "barishal"), ("BD1079", "Pirojpur", "পিরোজপুর", "barishal"),
    ("BD2003", "Bandarban", "বান্দরবান", "chattogram"), ("BD2012", "Brahmanbaria", "ব্রাহ্মণবাড়িয়া", "chattogram"),
    ("BD2013", "Chandpur", "চাঁদপুর", "chattogram"), ("BD2015", "Chattogram", "চট্টগ্রাম", "chattogram"),
    ("BD2019", "Cumilla", "কুমিল্লা", "chattogram"), ("BD2022", "Cox's Bazar", "কক্সবাজার", "chattogram"),
    ("BD2030", "Feni", "ফেনী", "chattogram"), ("BD2046", "Khagrachhari", "খাগড়াছড়ি", "chattogram"),
    ("BD2051", "Lakshmipur", "লক্ষ্মীপুর", "chattogram"), ("BD2075", "Noakhali", "নোয়াখালী", "chattogram"),
    ("BD2084", "Rangamati", "রাঙ্গামাটি", "chattogram"),
    ("BD3026", "Dhaka", "ঢাকা", "dhaka"), ("BD3029", "Faridpur", "ফরিদপুর", "dhaka"),
    ("BD3033", "Gazipur", "গাজীপুর", "dhaka"), ("BD3035", "Gopalganj", "গোপালগঞ্জ", "dhaka"),
    ("BD3048", "Kishoreganj", "কিশোরগঞ্জ", "dhaka"), ("BD3054", "Madaripur", "মাদারীপুর", "dhaka"),
    ("BD3056", "Manikganj", "মানিকগঞ্জ", "dhaka"), ("BD3059", "Munshiganj", "মুন্সিগঞ্জ", "dhaka"),
    ("BD3067", "Narayanganj", "নারায়ণগঞ্জ", "dhaka"), ("BD3068", "Narsingdi", "নরসিংদী", "dhaka"),
    ("BD3082", "Rajbari", "রাজবাড়ী", "dhaka"), ("BD3086", "Shariatpur", "শরীয়তপুর", "dhaka"),
    ("BD3093", "Tangail", "টাঙ্গাইল", "dhaka"),
    ("BD4001", "Bagerhat", "বাগেরহাট", "khulna"), ("BD4018", "Chuadanga", "চুয়াডাঙ্গা", "khulna"),
    ("BD4041", "Jashore", "যশোর", "khulna"), ("BD4044", "Jhenaidah", "ঝিনাইদহ", "khulna"),
    ("BD4047", "Khulna", "খুলনা", "khulna"), ("BD4050", "Kushtia", "কুষ্টিয়া", "khulna"),
    ("BD4055", "Magura", "মাগুরা", "khulna"), ("BD4057", "Meherpur", "মেহেরপুর", "khulna"),
    ("BD4065", "Narail", "নড়াইল", "khulna"), ("BD4087", "Satkhira", "সাতক্ষীরা", "khulna"),
    ("BD4539", "Jamalpur", "জামালপুর", "mymensingh"), ("BD4561", "Mymensingh", "ময়মনসিংহ", "mymensingh"),
    ("BD4572", "Netrokona", "নেত্রকোণা", "mymensingh"), ("BD4589", "Sherpur", "শেরপুর", "mymensingh"),
    ("BD5010", "Bogura", "বগুড়া", "rajshahi"), ("BD5038", "Joypurhat", "জয়পুরহাট", "rajshahi"),
    ("BD5064", "Naogaon", "নওগাঁ", "rajshahi"), ("BD5069", "Natore", "নাটোর", "rajshahi"),
    ("BD5070", "Chapainawabganj", "চাঁপাইনবাবগঞ্জ", "rajshahi"), ("BD5076", "Pabna", "পাবনা", "rajshahi"),
    ("BD5081", "Rajshahi", "রাজশাহী", "rajshahi"), ("BD5088", "Sirajganj", "সিরাজগঞ্জ", "rajshahi"),
    ("BD5527", "Dinajpur", "দিনাজপুর", "rangpur"), ("BD5532", "Gaibandha", "গাইবান্ধা", "rangpur"),
    ("BD5549", "Kurigram", "কুড়িগ্রাম", "rangpur"), ("BD5552", "Lalmonirhat", "লালমনিরহাট", "rangpur"),
    ("BD5573", "Nilphamari", "নীলফামারী", "rangpur"), ("BD5577", "Panchagarh", "পঞ্চগড়", "rangpur"),
    ("BD5585", "Rangpur", "রংপুর", "rangpur"), ("BD5594", "Thakurgaon", "ঠাকুরগাঁও", "rangpur"),
    ("BD6036", "Habiganj", "হবিগঞ্জ", "sylhet"), ("BD6058", "Moulvibazar", "মৌলভীবাজার", "sylhet"),
    ("BD6090", "Sunamganj", "সুনামগঞ্জ", "sylhet"), ("BD6091", "Sylhet", "সিলেট", "sylhet"),
]

MFS_PROVIDERS = [
    ("rocket", "ROCKET", "রকেট", "Dutch Bangla Bank PLC."),
    ("bkash", "bKash", "বিকাশ", "bKash Ltd."),
    ("mycash", "MYCash", "মাইক্যাশ", "Mercantile Bank PLC."),
    ("mcash", "Islami Bank mCash", "এমক্যাশ", "Islami Bank Bangladesh PLC."),
    ("tap", "Trust And Pay: tap", "ট্যাপ", "Trust And Pay Ltd."),
    ("firstcash", "FirstCash", "ফার্স্টক্যাশ", "First Security Islami Bank PLC."),
    ("upay", "Upay", "উপায়", "UCB Fintech Company Ltd."),
    ("ok_wallet", "OK Wallet", "ওকে ওয়ালেট", "One Bank PLC."),
    ("rupalicash", "RUPALICASH", "রূপালীক্যাশ", "Rupali Bank PLC."),
    ("telecash", "TeleCash", "টেলিক্যাশ", "Southeast Bank PLC."),
    ("islamic_wallet", "Islamic Wallet", "ইসলামিক ওয়ালেট", "Al-Arafah Islami Bank PLC."),
    ("meghna_pay", "Meghna Pay", "মেঘনা পে", "Meghna Bank PLC."),
    ("nagad", "Nagad", "নগদ", "Bangladesh Post Office (interim BB approval)"),
    ("lenden", "LENDEN", "লেনদেন", "Prime Bank FinTech Limited"),
]


def rows() -> list[dict]:
    result = [{
        "code": code, "kind": "division", "parent_code": None,
        "label_en": en, "label_bn": bn, "details": None,
        "source_url": NAME_SOURCE, "verified_on": VERIFIED_ON,
    } for code, en, bn in DIVISIONS]
    result += [{
        "code": code, "kind": "district", "parent_code": parent,
        "label_en": en, "label_bn": bn, "details": None,
        "source_url": DISTRICT_SOURCE, "verified_on": VERIFIED_ON,
    } for code, en, bn, parent in DISTRICTS]
    result += [{
        "code": code, "kind": "mfs_provider", "parent_code": None,
        "label_en": en, "label_bn": bn, "details": entity,
        "source_url": MFS_SOURCE, "verified_on": VERIFIED_ON,
    } for code, en, bn, entity in MFS_PROVIDERS]
    return result
