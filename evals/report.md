# Evaluation — eng-checkout-001

8 hand-labelled work events, of which 2 are genuine billable extras.

Accuracy alone is not reported as a headline because the two error classes are not
comparable: **overbilled** means a client was charged for work that was inside scope or
for a message containing no work, and **missed** means real work never reached the bill.

| arm | accuracy | precision | recall | overbilled | missed | uncited | $ overbilled | $ missed |
|---|---|---|---|---|---|---|---|---|
| keyword-baseline | 12% | 0% | 0% | 2 | 2 | 0 | $170.00 | $425.00 |
| gpt-6.1-sol | 100% | 100% | 100% | 0 | 0 | 0 | $0.00 | $0.00 |

## Where each arm went wrong

**keyword-baseline**
- overbilled: e1, e4
- missed: e3, e8
- billed without citing a clause: none

**gpt-6.1-sol**
- overbilled: none
- missed: none
- billed without citing a clause: none
