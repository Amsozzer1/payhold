from payhold.extract import normalize as nz


def test_money():
    assert nz.money("$1,850.00") == 185000
    assert nz.money("1850.00 USD") == 185000
    assert nz.money("$0.05") == 5
    assert nz.money("") is None


def test_dates():
    assert nz.date("2026-03-04") == "2026-03-04"
    assert nz.date("Mar 4, 2026") == "2026-03-04"
    assert nz.date("March 4, 2026") == "2026-03-04"
    assert nz.date("4/3/26") is None


def test_identifiers():
    assert nz.load_no("482-0157") == nz.load_no("4820157") == "4820157"
    assert nz.bol_no("3041 8827") == nz.bol_no("BOL-30418827") == "30418827"
    assert nz.invoice_no("INV-1043") == nz.invoice_no("1043") == "1043"
    assert nz.digits("USDOT 99123456") == "99123456"


def test_names_strip_suffixes_and_punctuation():
    assert nz.name("REDBIRD FREIGHT, L.L.C.") == nz.name("Redbird Freight LLC") == "REDBIRD FREIGHT"
    assert nz.name("Big Sky Lines Co") == "BIG SKY LINES"
    assert nz.name("Redbird Freight Inc") == nz.name("Redbird Freight Corp")
    assert nz.name("Redbird Freight") != nz.name("Redbird Hauling")


def test_charge_descriptions():
    assert nz.desc("Stop-off") == nz.desc("STOP-OFF") == "STOPOFF"
