"""Deterministic business turns and reviewable retail actions for Soundbox."""
import re
from datetime import datetime,timedelta,timezone
from uuid import uuid4

from sqlalchemy import select

from app.models import Product
from app.services.business_analytics import business_summary
from app.services.campaigns import money
from app.services.events import emit

ALIASES={
    'rice':r'\brice\b|\bchawal\b|चावल|तांदूळ|तांदुळ',
    'biscuit':r'\bbiscuits?\b|बिस्किट|बिस्कुट',
    'atta':r'\batta\b|\bwheat flour\b|आटा|पीठ',
    'oil':r'\boil\b|\btel\b|तेल',
    'salt':r'\bsalt\b|\bnamak\b|नमक|मीठ',
    'sugar':r'\bsugar\b|\bshakkar\b|चीनी|साखर',
    'tea':r'\btea\b|\bchai\b|चाय|चहा',
    'poha':r'\bpoha\b|पोहा|पोहे',
    'dal':r'\bdal\b|\bpulses\b|दाल|डाळ',
}
UNITS=r'(?:kilograms?|kilos?|kgs?|किलो|किलोग्राम|litres?|liters?|ltr|l|लीटर|लिटर|packets?|packs?|पैकेट|पॅकेट|bags?|units?|pieces?|pcs|नग)'


def normalized(text):
    text=text.casefold().translate(str.maketrans('०१२३४५६७८९','0123456789'))
    for word,number in {'एक':'1','दो':'2','तीन':'3','चार':'4','पांच':'5','पाँच':'5','one':'1','two':'2','three':'3','four':'4','five':'5'}.items():
        text=re.sub(r'(?<!\w)'+word+r'(?!\w)',number,text)
    return ' '.join(text.split())


def business_intent(text):
    text=normalized(text)
    # Product sale instructions are distinct from "what sold last week?" queries.
    if re.search(r'\bsold\b|\bbecha\b|\bbechi\b|बेचा|बेची|बेचे|विकले|विक्री नोंद',text) and re.search(r'\d',text):
        return 'sale'
    if re.search(r'\breorder\b|माल मंगा|माल मंगवा|स्टॉक मंगा|order bana|stock.*order|मागणी तयार',text):
        return 'reorder'
    patterns=[
        ('expiry',r'expir|एक्सपाय|खराब होने|खराब हो|मुदत|कालबाह्य'),
        ('stock',r'low.?stock|stock.*(?:kam|low|kitna)|कम.*स्टॉक|स्टॉक.*कम|माल.*कम|स्टॉक किती'),
        ('health',r'business.*health|health.*score|दुकान.*स्वास्थ्य|बिजनेस.*हेल्थ|व्यवसाय.*आरोग्य'),
        ('forecast',r'forecast|predict|अगले.*(?:दिन|हफ्ते).*बिक्री|पुढील.*विक्री|agle.*(?:hafte|din).*bik'),
        ('combinations',r'combination|basket|saath.*bik|साथ.*बिक|एकत्र.*विक'),
        ('peak_hours',r'peak|busy|भीड़|भीड़|व्यस्त|गर्दी'),
        ('wait_times',r'wait.*time|waiting|इंतजार|प्रतीक्षा'),
        ('best_sellers',r'best.?sell|top.*product|what.*sold|sold.*(?:week|best)|मागील.*आठवड|kya.*bika|kya.*bik|kaun.*bika|pichle.*hafte|पिछले.*हफ्ते|कौन.*बिका|क्या.*बिका|क्या.*बिक|सर्वाधिक.*विक'),
        ('summary',r'summary|सारांश|aaj.*(?:sale|sales|profit|munafa|kamai|revenue)|आज.*(?:बिक्री|मुनाफा|कमाई|खर्च)|आजचा|net.*profit|gross.*profit|कितना.*मुनाफा'),
    ]
    return next((intent for intent,pattern in patterns if re.search(pattern,text)),None)


def sale_draft(db,text):
    """Resolve every mentioned line; an ambiguous SKU never becomes a default item."""
    text=normalized(text)
    products=list(db.scalars(select(Product).where(Product.merchant_id=='sharma-kirana')).all())
    fragments=re.split(r'\s+(?:aur|and|और|आणि)\s+|[,;]',text)
    lines=[];unresolved=[]
    for fragment in fragments:
        quantity=re.search(r'(?<![\w.])(\d+(?:\.\d+)?)\s*('+UNITS+r')?(?!\w)',fragment)
        if not quantity:
            # Ignore a standalone payment-method clause, never a possible item line.
            if re.search(r'\b(?:cash|upi|payment)\b|नकद|यूपीआई',fragment) and not any(re.search(pattern,fragment) for pattern in ALIASES.values()):
                continue
            unresolved.append({'text':fragment,'reason':'Specify a whole positive quantity and product/variant.','candidates':[]})
            continue
        value=float(quantity.group(1))
        if value<=0 or value!=int(value) or value>100000:
            unresolved.append({'text':fragment,'reason':'Only positive whole catalogue units can be recorded.','candidates':[]})
            continue
        stripped=fragment[quantity.end():]
        # Longest exact catalogue names take priority over a generic grocery alias.
        exact=[p for p in products if normalized(p.name) in stripped]
        if exact:
            length=max(len(normalized(p.name)) for p in exact)
            candidates=[p for p in exact if len(normalized(p.name))==length]
        else:
            keys=[key for key,pattern in ALIASES.items() if re.search(pattern,stripped)]
            candidates=[p for p in products if any(re.search(ALIASES[key],p.name.casefold()) for key in keys)]
        if len(candidates)>1:
            variant_matches=[p for p in candidates if p.variant and p.variant.casefold()!='standard' and normalized(p.variant) in stripped]
            if variant_matches:
                candidates=variant_matches
        if len(candidates)!=1:
            unresolved.append({'text':fragment,'reason':'Choose the exact product and variant.' if candidates else 'No catalogue match; specify the exact product name.',
                'candidates':[{'product_id':p.id,'name':p.name,'variant':p.variant,'unit':p.unit,'unit_price':p.selling_price} for p in candidates]})
            continue
        product=candidates[0]
        spoken_unit=(quantity.group(2) or '').casefold()
        # A 5kg bag is sold as one catalogue bag. Never reinterpret "2kg atta" as two 5kg bags.
        if spoken_unit and (re.search(r'kg|kilo|किलो',spoken_unit) and product.unit.casefold() not in {'kg','kilogram','kilograms','किलो'} or
                            re.search(r'lit|ltr|लीटर|लिटर',spoken_unit) and product.unit.casefold() not in {'l','litre','liter','litres','liters','लीटर','लिटर'} or
                            re.search(r'packet|pack|पैकेट|पॅकेट',spoken_unit) and not re.search(r'packet|pack|पैकेट|पॅकेट',product.unit.casefold())):
            unresolved.append({'text':fragment,'reason':f'This SKU is sold in {product.unit}; specify a quantity of that catalogue unit.',
                               'candidates':[{'product_id':product.id,'name':product.name,'variant':product.variant,'unit':product.unit}]})
            continue
        lines.append({'product_id':product.id,'name':product.name,'variant':product.variant,'quantity':int(value),
                      'unit':product.unit,'expected_unit_price':product.selling_price,'line_total':money(product.selling_price*value)})
    # Duplicate phrases refer to one exact SKU; combine quantities visibly before review.
    combined={}
    for line in lines:
        if line['product_id'] in combined:
            combined[line['product_id']]['quantity']+=line['quantity']
            combined[line['product_id']]['line_total']=money(combined[line['product_id']]['quantity']*line['expected_unit_price'])
        else:
            combined[line['product_id']]=line
    payment='credit' if re.search(r'\bcredit\b|\budhar\b|उधार',text) else ('upi' if re.search(r'\bupi\b|यूपीआई',text) else 'cash')
    token=re.search(r'\bpk-\d{4}\b',text)
    if payment=='credit' and not token:
        unresolved.append({'text':'credit sale','reason':'Specify a saved customer token such as PK-0036 for credit; walk-in credit cannot be assigned to an unknown customer.','candidates':[]})
    return {'items':list(combined.values()),'unresolved':unresolved,'payment_method':payment,
            'customer_token':token.group().upper() if token else None,'total_amount':money(sum(line['line_total'] for line in combined.values()))}


def store_turn(db,row,data,response,business,proposal=None):
    messages=[*row.payload.get('messages',[]),
        {'role':'user','text':data.text,'language':data.language,'created_at':datetime.now(timezone.utc).isoformat()},
        {'role':'assistant','text':response,'provider':'merchant-data','demo':False,'business':business,
         'created_at':datetime.now(timezone.utc).isoformat()}][-50:]
    row.payload={**row.payload,'messages':messages,'proposal':proposal,'business':business,'language':data.language}
    emit(db,'voice.proposal' if proposal else 'voice.business','Business action ready for review' if proposal else 'Business question answered from recorded data',
         'No action runs without approval.' if proposal else business.get('intent','summary'),agent='voice',data={'session_id':row.id,'intent':business.get('intent')})
    db.commit()
    return {'session_id':row.id,'transcript':data.text,'response':response,'proposal':proposal,'business':business,
            'provider':'merchant-data','demo':False,'error':None,'messages':messages}


def business_turn(db,row,data,previous):
    intent=business_intent(data.text)
    if not intent:
        return None
    expires=(datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat()
    if intent=='sale':
        draft=sale_draft(db,data.text)
        if draft['unresolved'] or not draft['items']:
            details='; '.join(item['reason'] for item in draft['unresolved'])
            response={'hi-IN':f'बिक्री अभी दर्ज नहीं हुई। सही उत्पाद, वैरिएंट और मात्रा बताइए। {details}',
                      'mr-IN':f'विक्री नोंदवली नाही. योग्य उत्पादन, व्हेरियंट आणि प्रमाण सांगा. {details}',
                      'en-IN':f'No sale recorded. Please clarify the exact products, variants and quantities. {details}'}[data.language]
            return store_turn(db,row,data,response,{'intent':'sale','draft':draft,'review_required':True})
        listing=', '.join(f'{line["quantity"]} {line["unit"]} {line["name"]} ({line["variant"]})' for line in draft['items'])
        response={'hi-IN':f'{listing} की ₹{draft["total_amount"]:g} बिक्री का प्रस्ताव तैयार है ({draft["payment_method"]})। जाँचकर हाँ कहें। अभी स्टॉक या हिसाब नहीं बदला है।',
                  'mr-IN':f'{listing}, ₹{draft["total_amount"]:g} विक्रीचा प्रस्ताव तयार ({draft["payment_method"]}). तपासून हो म्हणा. स्टॉक किंवा हिशोब अजून बदललेला नाही.',
                  'en-IN':f'Review sale: {listing}, total ₹{draft["total_amount"]:g}, payment {draft["payment_method"]}. Say yes to record it. Stock and ledger have not changed yet.'}[data.language]
        proposal={'id':str(uuid4()),'action':'create_sale','status':'pending_approval','expires_at':expires,
                  'parameters':{'items':[{'product_id':line['product_id'],'quantity':line['quantity'],'expected_unit_price':line['expected_unit_price']} for line in draft['items']],
                                'payment_method':draft['payment_method'],'source':'voice',**({'customer_token':draft['customer_token']} if draft['customer_token'] else {})},
                  'review':draft}
        return store_turn(db,row,data,response,{'intent':'sale','draft':draft,'review_required':True},proposal)
    days=1 if intent=='summary' and re.search(r'aaj|आज|today',data.text.casefold()) else 7
    summary=business_summary(db,days)
    business={'intent':intent,**summary}
    if intent=='reorder':
        orders=defaultdict_orders(summary['inventory']['low_stock'])
        if orders:
            cost=money(sum(order['estimated_cost'] for order in orders))
            proposal={'id':str(uuid4()),'action':'create_reorders','status':'pending_approval','expires_at':expires,'parameters':{'orders':orders}}
            response={'hi-IN':f'{len(orders)} सप्लायर के लिए कम स्टॉक का ड्राफ्ट ऑर्डर तैयार है। मात्रा जाँचकर हाँ कहें। कोई संदेश या भुगतान नहीं भेजा जाएगा।',
                      'mr-IN':f'{len(orders)} पुरवठादारांसाठी कमी स्टॉकचे ड्राफ्ट ऑर्डर तयार. प्रमाण तपासून हो म्हणा. संदेश किंवा पैसे पाठवले जाणार नाहीत.',
                      'en-IN':f'Review {len(orders)} supplier reorder drafts for low-stock products. Say yes to save drafts. No supplier message or payment will be sent.'}[data.language]
            return store_turn(db,row,data,response,business,proposal)
        response={'hi-IN':'अभी कोई उत्पाद तय रीऑर्डर स्तर पर या उससे कम नहीं है। कोई ऑर्डर नहीं बनाया।',
                  'mr-IN':'सध्या कोणतेही उत्पादन रीऑर्डर पातळीवर किंवा खाली नाही. ऑर्डर तयार केली नाही.',
                  'en-IN':'No product is currently at or below its reorder point. No reorder was created.'}[data.language]
    else:
        response=business_answer(summary,intent,data.language)
    # Read-only questions keep the visible pending proposal unchanged for subsequent approval.
    pending=previous if previous and previous.get('status')=='pending_approval' else None
    return store_turn(db,row,data,response,business,pending)


def defaultdict_orders(low_stock):
    orders={}
    for product in low_stock:
        order=orders.setdefault(product['supplier'],{'supplier':product['supplier'],'items':[],'estimated_cost':0})
        order['items'].append({'product_id':product['product_id'],'quantity':product['suggested_quantity']})
    return list(orders.values())


def business_answer(summary,intent,language):
    sales=summary['sales'];days=summary['period']['days']
    hindi=language=='hi-IN';marathi=language=='mr-IN'
    if intent=='best_sellers':
        items=summary['best_sellers'][:3]
        listing='; '.join(f'{item["name"]} ({item["variant"]}): {item["quantity"]:g}, ₹{item["revenue"]:g}' for item in items)
        if not listing:
            return 'अभी उत्पाद वाली बिक्री का रिकॉर्ड नहीं है; पुराने कुल बिलों से उत्पाद नहीं बता सकता।' if hindi else ('उत्पादननिहाय विक्री नोंद नाही; जुन्या एकूण बिलांत उत्पादन तपशील नाही.' if marathi else 'No itemized sales are recorded in this period. Older bill totals cannot identify products.')
        return (f'पिछले {days} दिनों की उत्पाद वाली बिक्री में सबसे अधिक: {listing}। पुराने बिना उत्पाद वाले बिल इसमें शामिल नहीं हैं।' if hindi else
                f'मागील {days} दिवसांच्या उत्पादननिहाय विक्रीत सर्वाधिक: {listing}. जुन्या एकूण बिलांचा यात समावेश नाही.' if marathi else
                f'Top recorded item sales over {days} days: {listing}. Historical bill totals without product lines are excluded.')
    if intent in {'stock','expiry'}:
        items=summary['inventory']['low_stock'] if intent=='stock' else summary['inventory']['expired']+summary['inventory']['expiring']
        if not items:
            return ('अभी कोई कम स्टॉक वाला उत्पाद नहीं मिला।' if intent=='stock' else 'दर्ज बैचों में अगले 14 दिनों में समाप्त होने वाला या पहले से एक्सपायर माल नहीं मिला।') if hindi else ('कमी स्टॉक आढळला नाही.' if intent=='stock' else 'नोंदलेल्या बॅचमध्ये कालबाह्य किंवा 14 दिवसांत संपणारी मुदत नाही.') if marathi else ('No product is below its recorded reorder point.' if intent=='stock' else 'No recorded batch is expired or expires within 14 days.')
        listing='; '.join(f'{item["name"]} ({item["variant"]}): {item["quantity"]}, '+(f'reorder {item["reorder_point"]}' if intent=='stock' else f'expires {item["expires_on"]}') for item in items[:4])
        return ('स्टॉक की जाँच: ' if hindi else 'स्टॉक तपासणी: ' if marathi else 'Recorded stock review: ')+listing+('।' if hindi else '.')
    if intent=='health':
        score=summary['health']['score'];label=f'{score:g}/100' if score is not None else 'unavailable'
        missing=', '.join(component['name'] for component in summary['health']['components'] if not component['available']) or 'none'
        return (f'दुकान का जानकारी आधारित हेल्थ स्कोर {label} है। बिक्री, मार्जिन, स्टॉक और दर्ज खर्च के उपलब्ध प्रमाण से गणना हुई है। अधूरा प्रमाण: {missing}। यह अनुमानित सूचक है, क्रेडिट स्कोर नहीं।' if hindi else
                f'व्यवसाय हेल्थ स्कोर {label}. उपलब्ध विक्री, मार्जिन, स्टॉक व खर्चावर आधारित. अपुरा पुरावा: {missing}. हा मार्गदर्शक संकेत आहे.' if marathi else
                f'Business health is {label}, a transparent heuristic based on available sales, margin, inventory and expense records. Missing evidence: {missing}. This is not a credit score.')
    if intent=='forecast':
        forecast=summary['forecast'];total=money(sum(day['revenue'] for day in forecast['daily']))
        error=f'₹{forecast["backtest_mae"]:g}' if forecast['backtest_mae'] is not None else 'unavailable'
        return (f'अगले 7 दिनों की कुल बिक्री का सांख्यिकीय अनुमान ₹{total:g} है। {forecast["sample_days"]} पूरे दिनों के रिकॉर्ड; तरीका {forecast["method"]}; परीक्षण की औसत गलती {error}। यह गारंटी नहीं है।' if hindi else
                f'पुढील 7 दिवसांचा सांख्यिकीय विक्री अंदाज ₹{total:g}. {forecast["sample_days"]} पूर्ण दिवस; पद्धत {forecast["method"]}; चाचणीची सरासरी चूक {error}. हमी नाही.' if marathi else
                f'The next 7 days project ₹{total:g} recorded revenue using {forecast["method"]}, trained on {forecast["sample_days"]} complete days. Rolling backtest mean absolute error: {error}. This is an estimate, not a guarantee.')
    if intent=='wait_times':
        return 'ग्राहक आने और सेवा शुरू होने का समय दर्ज नहीं है, इसलिए प्रतीक्षा का समय नहीं बता सकता।' if hindi else ('ग्राहक आगमन व सेवा सुरू होण्याची वेळ नोंद नाही; प्रतीक्षा वेळ मोजता येत नाही.' if marathi else summary['wait_times']['reason'])
    if intent=='peak_hours':
        top=summary['peak_hours'][:3]
        text='; '.join(f'{hour["label"]}: {hour["transactions"]}' for hour in top)
        return ('दर्ज बिलों की सबसे व्यस्त अवधि: ' if hindi else 'नोंदलेल्या बिलांची गर्दीची वेळ: ' if marathi else 'Busiest recorded transaction hours: ')+(text or 'No recorded transactions')+'.'
    if intent=='combinations':
        pairs=summary['product_combinations'][:3]
        text='; '.join(' + '.join(product['name'] for product in pair['products'])+f': {pair["basket_count"]} baskets' for pair in pairs)
        return ('एक ही बिल में खरीदे गए उत्पाद: ' if hindi else 'एका बिलात विकलेली उत्पादने: ' if marathi else 'Products bought in the same recorded basket: ')+(text or 'No same-basket item evidence')+'.'
    return (f'पिछले {days} दिन: बिक्री ₹{sales["revenue"]:g}, सकल लाभ ₹{sales["gross_profit"]:g}, दर्ज खर्च ₹{sales["expenses"]:g}। दर्ज खर्च के बाद ₹{sales["net_profit"]:g} बचता है; बिना दर्ज खर्च अज्ञात हैं।' if hindi else
            f'मागील {days} दिवस: विक्री ₹{sales["revenue"]:g}, ढोबळ नफा ₹{sales["gross_profit"]:g}, नोंदलेला खर्च ₹{sales["expenses"]:g}; नंतर ₹{sales["net_profit"]:g}. न नोंदलेले खर्च अज्ञात.' if marathi else summary['summary_text'])
