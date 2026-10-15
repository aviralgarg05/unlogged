# Evaluation — eng-checkout-001

8 hand-labelled work events, of which 2 are genuine billable extras.

Accuracy alone is not reported as a headline because the two error classes are not
comparable: **overbilled** means a client was charged for work that was inside scope or
for a message containing no work, and **missed** means real work never reached the bill.

| arm | accuracy | precision | recall | overbilled | missed | uncited | $ overbilled | $ missed | hours wrong | $ hour error |
|---|---|---|---|---|---|---|---|---|---|---|
| keyword-baseline | 12% | 0% | 0% | 2 | 2 | 0 | $170.00 | $425.00 | 0 | $0.00 |
| gpt-6.1-sol | 100% | 100% | 100% | 0 | 0 | 0 | $0.00 | $0.00 | 1 | -$42.50 |

## What the labels are worth

A label is only as good as where it came from, and these are not equal:

| provenance | labels | what it means |
|---|---|---|
| authored | 8 | written for this repository by the author of the arm being measured |

**8 of 8 labels were written for this repository.** An arm scoring well against those has agreed with its own author.

## Where each arm went wrong

**keyword-baseline**
- overbilled: e1, e4
- missed: e3, e8
- billed without citing a clause: none
- cited a clause not yet in force: none
- right call, wrong hours: none

**gpt-6.1-sol**
- overbilled: none
- missed: none
- billed without citing a clause: none
- cited a clause not yet in force: none
- right call, wrong hours: e8 (-$42.50 to the client)
