from payhold.checks import bank_change, documents, double_brokering, double_factoring, padding, rebill

# Order only affects the order reasons are listed in.
CHECKS = [documents.check, padding.check, rebill.check, double_factoring.check, bank_change.check, double_brokering.check]
