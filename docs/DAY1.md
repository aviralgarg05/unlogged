> **Note.** Raw bodies from the opening verification run. See `VERIFIED.md` for what these
> established, and `HONESTY.md` for which mechanism the product actually ships.

# Day-1 gate — 2026-10-15

Can a PayPal invoice's charged amount really move while its printed QR stays valid?


| Check | Result |
|---|---|
| create | PASS |
| discount persisted | PASS |
| silent send | PASS |
| qr | PASS |
| price move | PASS |
| payer page charges the moved amount (manual) | PASS |

## Raw exchanges

### Check 1 — create

`POST /v2/invoicing/invoices` -> **201**
Request:
```json
{
  "detail": {
    "currency_code": "GBP",
    "invoice_date": "2026-10-15",
    "reference": "lot-001",
    "memo": "cut sourdough, half tray | shelf-life bucket SHORT | confidence 0.82",
    "payment_term": {
      "term_type": "DUE_ON_RECEIPT"
    }
  },
  "invoicer": {
    "business_name": "Shelfmark Test Bakery"
  },
  "items": [
    {
      "name": "Half tray, cut sourdough",
      "quantity": "1",
      "unit_amount": {
        "currency_code": "GBP",
        "value": "4.00"
      },
      "unit_of_measure": "QUANTITY"
    }
  ],
  "amount": {
    "currency_code": "GBP",
    "breakdown": {
      "discount": {
        "invoice_discount": {
          "percent": "25"
        }
      }
    }
  }
}
```
Response:
```
{"id":"INV2-YXDC-QV7M-XGM2-H9F9","status":"DRAFT","detail":{"reference":"lot-001","currency_code":"GBP","memo":"cut sourdough, half tray | shelf-life bucket SHORT | confidence 0.82","category_code":"SHIPPABLE","invoice_number":"0008","invoice_date":"2026-10-15","payment_term":{"term_type":"DUE_ON_RECEIPT","due_date":"2026-10-15"},"viewed_by_recipient":false,"group_draft":false,"metadata":{"create_time":"2026-10-15T08:06:33Z","last_update_time":"2026-10-15T08:06:33Z","created_by_flow":"REGULAR_SINGLE","recipient_view_url":"https://www.sandbox.paypal.com/invoice/p/#YXDCQV7MXGM2H9F9","invoicer_view_url":"https://www.sandbox.paypal.com/invoice/details/INV2-YXDC-QV7M-XGM2-H9F9","caller_type":"API_V2_INVOICE","spam_info":{}},"archived":false},"invoicer":{"business_name":"Shelfmark Test Bakery"},"items":[{"id":"ITEM-3SC558641G921873L","name":"Half tray, cut sourdough","quantity":"1","unit_amount":{"currency_code":"GBP","value":"4.00"},"unit_of_measure":"QUANTITY"}],"configuration":{"tax_calculated_after_discount":false,"tax_inclusive":false,"allow_tip":false,"allow_only_pay_by_bank":false,"allow_vba_payments":false,"save_item_for_future":true,"template_id":"TEMP-7181852024373634C"},"amount":{"breakdown":{"item_total":{"currency_code":"GBP","value":"4.00"},"discount":{"invoice_discount":{"percent":"25","amount":{"currency_code":"GBP","value":"-1.00"}},"item_discount":{"currency_code":"GBP","value":"0.00"}},"tax_total":{"currency_code":"GBP","value":"0.00"}},"currency_code":"GBP","value":"3.00"},"due_amount":{"currency_code":"GBP","value":"3.00"},"links":[{"href":"https://api.sandbox.paypal.com/v2/invoicing/invoices/INV2-YXDC-QV7M-XGM2-H9F9","rel":"self","method":"GET"},{"href":"https://api.sandbox.paypal.com/v2/invoicing/invoices/INV2-YXDC-QV7M-XGM2-H9F9/send","rel":"send","method":"POST"},{"href":"https://api.sandbox.paypal.com/v2/invoicing/invoices/INV2-YXDC-QV7M-XGM2-H9F9","rel":"replace","method":"PUT"},{"href":"https://api.sandbox.paypal.com/v2/invoicing/invoices/INV2-YXDC-QV7M-XGM2-H9F9","rel":"delete","method":"DELETE"},{"href":"https://api.sandbox.paypal.com/v2/invoicing/invoices/INV2-YXDC-QV7M-XGM2-H9F9/payments","rel":"record-payment","method":"POST"}],"unilateral":false,"settings":{}}
```

**PASS — create.** HTTP 201

**PASS — discount persisted.** £4.00 list -> status=DRAFT total=3.00 due=3.00 discount=25% (-1.00)

### Check 2 — silent send

`POST /v2/invoicing/invoices/INV2-YXDC-QV7M-XGM2-H9F9/send` -> **200**
Request:
```json
{
  "send_to_recipient": false,
  "send_to_invoicer": false
}
```
Response:
```
{"href":"https://www.sandbox.paypal.com/invoice/p/#INV2-YXDC-QV7M-XGM2-H9F9","rel":"payer-view","method":"GET"}
```

**PASS — silent send.** status=UNPAID total=3.00 due=3.00 discount=25% (-1.00) (payable, no email sent)

### Check 3 — QR

`POST /v2/invoicing/invoices/INV2-YXDC-QV7M-XGM2-H9F9/generate-qr-code` -> **200**
Request:
```json
{
  "width": 500,
  "height": 500,
  "action": "pay"
}
```
Response:
```
<multipart/form-data, 1448 bytes, base64 PNG in part 'image'>
```

**PASS — qr.** 968 byte PNG -> docs/day1_qr.png

### Check 4 — move to 50% off

`PUT /v2/invoicing/invoices/INV2-YXDC-QV7M-XGM2-H9F9` -> **200**
Request:
```json
{
  "id": "INV2-YXDC-QV7M-XGM2-H9F9",
  "detail": {
    "reference": "lot-001",
    "currency_code": "GBP",
    "memo": "cut sourdough, half tray | shelf-life bucket SHORT | confidence 0.82",
    "category_code": "SHIPPABLE",
    "invoice_number": "0008",
    "invoice_date": "2026-10-15",
    "payment_term": {
      "term_type": "DUE_ON_RECEIPT",
      "due_date": "2026-10-15"
    },
    "viewed_by_recipient": false,
    "group_draft": false,
    "metadata": {
      "create_time": "2026-10-15T08:06:33Z",
      "last_update_time": "2026-10-15T08:06:33Z",
      "created_by_flow": "REGULAR_SINGLE",
      "recipient_view_url": "https://www.sandbox.paypal.com/invoice/p/#YXDCQV7MXGM2H9F9",
      "invoicer_view_url": "https://www.sandbox.paypal.com/invoice/details/INV2-YXDC-QV7M-XGM2-H9F9",
      "caller_type": "API_V2_INVOICE",
      "spam_info": {}
    },
    "archived": false
  },
  "invoicer": {
    "business_name": "Shelfmark Test Bakery"
  },
  "items": [
    {
      "id": "ITEM-3SC558641G921873L",
      "name": "Half tray, cut sourdough",
      "quantity": "1",
      "unit_amount": {
        "currency_code": "GBP",
        "value": "4.00"
      },
      "unit_of_measure": "QUANTITY"
    }
  ],
  "configuration": {
    "tax_calculated_after_discount": false,
    "tax_inclusive": false,
    "allow_tip": false,
    "allow_only_pay_by_bank": false,
    "allow_vba_payments": false,
    "save_item_for_future": true,
    "template_id": "TEMP-7181852024373634C"
  },
  "amount": {
    "currency_code": "GBP",
    "breakdown": {
      "discount": {
        "invoice_discount": {
          "percent": "50"
        }
      }
    }
  },
  "unilateral": true,
  "settings": {}
}
```
Response:
```
{"id":"INV2-YXDC-QV7M-XGM2-H9F9","status":"UNPAID","detail":{"reference":"lot-001","currency_code":"GBP","memo":"cut sourdough, half tray | shelf-life bucket SHORT | confidence 0.82","category_code":"SHIPPABLE","invoice_number":"0008","invoice_date":"2026-10-15","payment_term":{"term_type":"DUE_ON_RECEIPT","due_date":"2026-10-15"},"viewed_by_recipient":false,"group_draft":false,"metadata":{"create_time":"2026-10-15T08:06:33Z","last_update_time":"2026-10-15T08:06:37Z","created_by_flow":"REGULAR_SINGLE","recipient_view_url":"https://www.sandbox.paypal.com/invoice/p/#YXDCQV7MXGM2H9F9","invoicer_view_url":"https://www.sandbox.paypal.com/invoice/details/INV2-YXDC-QV7M-XGM2-H9F9","caller_type":"API_V2_INVOICE","spam_info":{}},"archived":false},"invoicer":{"business_name":"Shelfmark Test Bakery"},"items":[{"id":"ITEM-3SC558641G921873L","name":"Half tray, cut sourdough","quantity":"1","unit_amount":{"currency_code":"GBP","value":"4.00"},"unit_of_measure":"QUANTITY"}],"configuration":{"tax_calculated_after_discount":false,"tax_inclusive":false,"allow_tip":false,"allow_only_pay_by_bank":false,"allow_vba_payments":false,"save_item_for_future":true,"template_id":"TEMP-7181852024373634C"},"amount":{"breakdown":{"item_total":{"currency_code":"GBP","value":"4.00"},"discount":{"invoice_discount":{"percent":"50","amount":{"currency_code":"GBP","value":"-2.00"}},"item_discount":{"currency_code":"GBP","value":"0.00"}},"tax_total":{"currency_code":"GBP","value":"0.00"}},"currency_code":"GBP","value":"2.00"},"due_amount":{"currency_code":"GBP","value":"2.00"},"links":[{"href":"https://api.sandbox.paypal.com/v2/invoicing/invoices/INV2-YXDC-QV7M-XGM2-H9F9","rel":"self","method":"GET"},{"href":"https://api.sandbox.paypal.com/v2/invoicing/invoices/INV2-YXDC-QV7M-XGM2-H9F9","rel":"replace","method":"PUT"},{"href":"https://api.sandbox.paypal.com/v2/invoicing/invoices/INV2-YXDC-QV7M-XGM2-H9F9/cancel","rel":"cancel","method":"POST"},{"href":"https://api.sandbox.paypal.com/v2/invoicing/invoices/INV2-YXDC-QV7M-XGM2-H9F9/remind","rel":"remind","method":"POST"},{"href":"https://api.sandbox.paypal.com/v2/invoicing/invoices/INV2-YXDC-QV7M-XGM2-H9F9/payments","rel":"record-payment","method":"POST"},{"href":"https://api.sandbox.paypal.com/v2/invoicing/invoices/INV2-YXDC-QV7M-XGM2-H9F9/generate-qr-code","rel":"qr-code","method":"GET"}],"unilateral":false,"settings":{}}
```

### Check 4 — move to 75% off

`PUT /v2/invoicing/invoices/INV2-YXDC-QV7M-XGM2-H9F9` -> **200**
Request:
```json
{
  "id": "INV2-YXDC-QV7M-XGM2-H9F9",
  "detail": {
    "reference": "lot-001",
    "currency_code": "GBP",
    "memo": "cut sourdough, half tray | shelf-life bucket SHORT | confidence 0.82",
    "category_code": "SHIPPABLE",
    "invoice_number": "0008",
    "invoice_date": "2026-10-15",
    "payment_term": {
      "term_type": "DUE_ON_RECEIPT",
      "due_date": "2026-10-15"
    },
    "viewed_by_recipient": false,
    "group_draft": false,
    "metadata": {
      "create_time": "2026-10-15T08:06:33Z",
      "last_update_time": "2026-10-15T08:06:37Z",
      "created_by_flow": "REGULAR_SINGLE",
      "recipient_view_url": "https://www.sandbox.paypal.com/invoice/p/#YXDCQV7MXGM2H9F9",
      "invoicer_view_url": "https://www.sandbox.paypal.com/invoice/details/INV2-YXDC-QV7M-XGM2-H9F9",
      "caller_type": "API_V2_INVOICE",
      "spam_info": {}
    },
    "archived": false
  },
  "invoicer": {
    "business_name": "Shelfmark Test Bakery"
  },
  "items": [
    {
      "id": "ITEM-3SC558641G921873L",
      "name": "Half tray, cut sourdough",
      "quantity": "1",
      "unit_amount": {
        "currency_code": "GBP",
        "value": "4.00"
      },
      "unit_of_measure": "QUANTITY"
    }
  ],
  "configuration": {
    "tax_calculated_after_discount": false,
    "tax_inclusive": false,
    "allow_tip": false,
    "allow_only_pay_by_bank": false,
    "allow_vba_payments": false,
    "save_item_for_future": true,
    "template_id": "TEMP-7181852024373634C"
  },
  "amount": {
    "currency_code": "GBP",
    "breakdown": {
      "discount": {
        "invoice_discount": {
          "percent": "75"
        }
      }
    }
  },
  "unilateral": false,
  "settings": {}
}
```
Response:
```
{"id":"INV2-YXDC-QV7M-XGM2-H9F9","status":"UNPAID","detail":{"reference":"lot-001","currency_code":"GBP","memo":"cut sourdough, half tray | shelf-life bucket SHORT | confidence 0.82","category_code":"SHIPPABLE","invoice_number":"0008","invoice_date":"2026-10-15","payment_term":{"term_type":"DUE_ON_RECEIPT","due_date":"2026-10-15"},"viewed_by_recipient":false,"group_draft":false,"metadata":{"create_time":"2026-10-15T08:06:33Z","last_update_time":"2026-10-15T08:06:39Z","created_by_flow":"REGULAR_SINGLE","recipient_view_url":"https://www.sandbox.paypal.com/invoice/p/#YXDCQV7MXGM2H9F9","invoicer_view_url":"https://www.sandbox.paypal.com/invoice/details/INV2-YXDC-QV7M-XGM2-H9F9","caller_type":"API_V2_INVOICE","spam_info":{}},"archived":false},"invoicer":{"business_name":"Shelfmark Test Bakery"},"items":[{"id":"ITEM-3SC558641G921873L","name":"Half tray, cut sourdough","quantity":"1","unit_amount":{"currency_code":"GBP","value":"4.00"},"unit_of_measure":"QUANTITY"}],"configuration":{"tax_calculated_after_discount":false,"tax_inclusive":false,"allow_tip":false,"allow_only_pay_by_bank":false,"allow_vba_payments":false,"save_item_for_future":true,"template_id":"TEMP-7181852024373634C"},"amount":{"breakdown":{"item_total":{"currency_code":"GBP","value":"4.00"},"discount":{"invoice_discount":{"percent":"75","amount":{"currency_code":"GBP","value":"-3.00"}},"item_discount":{"currency_code":"GBP","value":"0.00"}},"tax_total":{"currency_code":"GBP","value":"0.00"}},"currency_code":"GBP","value":"1.00"},"due_amount":{"currency_code":"GBP","value":"1.00"},"links":[{"href":"https://api.sandbox.paypal.com/v2/invoicing/invoices/INV2-YXDC-QV7M-XGM2-H9F9","rel":"self","method":"GET"},{"href":"https://api.sandbox.paypal.com/v2/invoicing/invoices/INV2-YXDC-QV7M-XGM2-H9F9","rel":"replace","method":"PUT"},{"href":"https://api.sandbox.paypal.com/v2/invoicing/invoices/INV2-YXDC-QV7M-XGM2-H9F9/cancel","rel":"cancel","method":"POST"},{"href":"https://api.sandbox.paypal.com/v2/invoicing/invoices/INV2-YXDC-QV7M-XGM2-H9F9/remind","rel":"remind","method":"POST"},{"href":"https://api.sandbox.paypal.com/v2/invoicing/invoices/INV2-YXDC-QV7M-XGM2-H9F9/payments","rel":"record-payment","method":"POST"},{"href":"https://api.sandbox.paypal.com/v2/invoicing/invoices/INV2-YXDC-QV7M-XGM2-H9F9/generate-qr-code","rel":"qr-code","method":"GET"}],"unilateral":false,"settings":{}}
```

**PASS — price move.** £3.00 -> £2.00 -> £1.00, invoice id stable throughout

### Check 5 — payer page (manual)

https://www.sandbox.paypal.com/invoice/payerView/details/INV2-YXDC-QV7M-XGM2-H9F9?qr=1

Must charge **£1.00** against a £4.00 list price. Verified green on 2026-10-15: the page renders `Subtotal £4.00 / Discount (75% off) -£3.00 / Total £1.00`, so PayPal shows the markdown itself — the strike-through is free.
