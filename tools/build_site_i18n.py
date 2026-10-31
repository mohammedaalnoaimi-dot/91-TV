"""Adds Arabic to the website: puts data-ar="<Arabic html>" on every English element listed below,
and adds the language button. Run from the repo root:  python3 tools/build_site_i18n.py
The page script (docs/site/i18n.js) swaps the text and flips the page to right-to-left."""
import re, sys
from bs4 import BeautifulSoup

MAIN = {
"Features":"المزايا","Picture & sound":"الصورة والصوت","Download":"التحميل","Pricing":"الأسعار","FAQ":"الأسئلة الشائعة","Try free":"جرّب مجانًا",
"For Android TV & Windows 11":"لأجهزة Android TV وWindows 11",
"Your IPTV, in its best light.":"خدمة IPTV الخاصة بك، في <em>أبهى صورة.</em>",
"91 TV turns your IPTV subscription into a cinema at home: a calm, beautiful interface for live TV, movies and series, with Dolby Vision, Dolby Atmos and a real TV guide.":"يحوّل 91 TV اشتراك IPTV الخاص بك إلى سينما في بيتك: واجهة هادئة وجميلة للبث المباشر والأفلام والمسلسلات، مع Dolby Vision وDolby Atmos ودليل برامج حقيقي.",
"Try free for 7 days":"جرّب مجانًا لمدة 7 أيام","See plans":"شاهد الخطط",
"7 days free · no card needed · then from 1.500 BHD":"7 أيام مجانًا · بدون بطاقة · ثم ابتداءً من 1.500 د.ب",
"platforms: Android TV & Windows 11":"منصتان: Android TV وWindows 11",
"Dolby Atmos & DTS passthrough":"تمرير Dolby Atmos وDTS",
"channels at once in Multi-view":"قنوات في وقت واحد بالعرض المتعدد",
"days free, no card":"أيام مجانًا بدون بطاقة","ads, ever":"إعلانات، أبدًا",
"The tour":"جولة في التطبيق",
"Everything you watch, in one calm place.":"كل ما تشاهده، في مكان واحد هادئ.",
"Add your provider once, by M3U link or Xtream Codes login, and 91 TV builds your home screen, guide and library automatically.":"أضف مزوّد الخدمة مرة واحدة برابط M3U أو ببيانات Xtream Codes، وسيبني 91 TV شاشتك الرئيسية والدليل والمكتبة تلقائيًا.",
"Live TV & guide":"البث المباشر والدليل",
"Know what's on, at a glance.":"اعرف ما يُعرض، بنظرة واحدة.",
"A full programme guide shows what's playing now, next and later tonight on every channel. Pick a show and it starts instantly.":"يعرض دليل البرامج الكامل ما يُعرض الآن وما بعده وما يُعرض لاحقًا الليلة على كل قناة. اختر برنامجًا ويبدأ فورًا.",
"XMLTV guide, now & next on every channel":"دليل XMLTV: الآن والتالي على كل قناة",
"Channel up / down from the remote":"تبديل القنوات بالأعلى والأسفل من جهاز التحكم",
"Live rewind buffer for the last few minutes":"إرجاع البث المباشر لآخر بضع دقائق",
"Hide the categories and languages you never watch":"أخفِ الفئات واللغات التي لا تشاهدها",
"TV Guide · illustration with sample channels":"دليل البرامج · رسم توضيحي بقنوات تجريبية",
"Multi-view":"العرض المتعدد",
"Four screens. One remote.":"أربع شاشات. جهاز تحكم واحد.",
"Follow several matches or news channels side by side. Only the screen you pick plays sound, and any screen goes full-screen with one press.":"تابع عدة مباريات أو قنوات إخبارية جنبًا إلى جنب. الصوت يعمل فقط على الشاشة التي تختارها، ويمكن تكبير أي شاشة بضغطة واحدة.",
"Up to 4 live channels at once":"حتى 4 قنوات مباشرة في وقت واحد",
"Choose which screen has the audio":"اختر الشاشة التي يصدر منها الصوت",
"Perfect for match days":"مثالي لأيام المباريات",
"Multi-view · illustration with sample channels":"العرض المتعدد · رسم توضيحي بقنوات تجريبية",
"Prayer times":"أوقات الصلاة",
"Built around your day.":"مصمم حول يومك.",
"Today's prayer times sit quietly in the top bar, with a gentle reminder before each prayer, in Arabic and English.":"تظهر أوقات الصلاة اليوم بهدوء في الشريط العلوي، مع تنبيه لطيف قبل كل صلاة، بالعربية والإنجليزية.",
"Fajr to Isha, calculated for your city":"من الفجر إلى العشاء، محسوبة لمدينتك",
"Gulf Region and other calculation methods":"منطقة الخليج وطرق حساب أخرى",
"Optional reminder before every prayer":"تنبيه اختياري قبل كل صلاة",
"Prayer times · real screen from 91 TV":"أوقات الصلاة · شاشة حقيقية من 91 TV",
"Ambient screensaver":"شاشة التوقف الهادئة",
"Beautiful, even when it's resting.":"جميل حتى وهو في وضع الراحة.",
"After a few quiet minutes, 91 TV fades to a soft clock with the date and your next prayer, gentle on OLED screens and lovely in a dark room.":"بعد بضع دقائق هادئة، ينتقل 91 TV إلى ساعة ناعمة مع التاريخ وصلاتك القادمة، لطيفة على شاشات OLED وجميلة في الغرفة المظلمة.",
"Clock, date and next prayer":"الساعة والتاريخ والصلاة القادمة",
"Or a slideshow of your library's artwork":"أو عرض صور من مكتبتك",
"Screensaver · real screen from 91 TV":"شاشة التوقف · شاشة حقيقية من 91 TV",
"The way the film was mastered.":"كما صُنع الفيلم تمامًا.",
"91 TV plays HDR and Dolby Vision itself, and sends Atmos straight to your TV or soundbar, so the picture and sound arrive exactly as they were made.":"يشغّل 91 TV صور HDR وDolby Vision بنفسه، ويرسل Atmos مباشرة إلى تلفازك أو مكبّر الصوت، فتصل الصورة والصوت كما صُنعا.",
"Your TV switches to Dolby Vision automatically":"يتحول تلفازك إلى Dolby Vision تلقائيًا",
"Scrub with picture previews":"تنقّل بمعاينة للصورة",
"Auto-reconnect when a stream drops":"إعادة اتصال تلقائية عند انقطاع البث",
"Player with scrub preview · illustration":"المشغّل مع معاينة التنقل · رسم توضيحي",
"Real HDR on supported TVs, with tone-mapping for SDR screens on Windows.":"HDR حقيقي على التلفزيونات المدعومة، مع تحويل الألوان لشاشات SDR على Windows.",
"Bitstream passthrough over HDMI and ARC to your soundbar or receiver.":"تمرير الصوت الخام عبر HDMI وARC إلى مكبّر الصوت أو الريسيفر.",
"Hardware decoding":"فك ترميز بالعتاد",
"Smooth playback on Android TV, and NVIDIA-accelerated on Windows.":"تشغيل سلس على Android TV، وبتسريع NVIDIA على Windows.",
"Your provider":"مزوّدك",
"Works with M3U / M3U8 playlists, Xtream Codes logins and XMLTV guides.":"يعمل مع قوائم M3U / M3U8 وبيانات Xtream Codes وأدلة XMLTV.",
"Two apps":"تطبيقان",
"On your TV and your PC.":"على تلفازك وحاسوبك.",
"91 TV for Android TV":"91 TV لـ Android TV",
"Built for the remote: every screen works with the arrow keys and OK. Installs in a minute with the free Downloader app.":"مصمم لجهاز التحكم: تعمل كل شاشة بأسهم التنقل وزر OK. يُثبَّت في دقيقة عبر تطبيق Downloader المجاني.",
"Android TV / Google TV · Android 5.0 or later · e.g. Sony, TCL, Skyworth, Hisense, Chromecast":"Android TV / Google TV · Android 5.0 أو أحدث · مثل Sony وTCL وSkyworth وHisense وChromecast",
"91 TV for Windows 11":"91 TV لـ Windows 11",
"The same cinema feel on your PC, with keyboard, mouse and Xbox controller support, HDR output and NVIDIA acceleration.":"الإحساس السينمائي نفسه على حاسوبك، مع دعم لوحة المفاتيح والفأرة وذراع Xbox، وإخراج HDR وتسريع NVIDIA.",
"Windows 10 / 11 · 64-bit · No admin rights needed":"Windows 10 / 11 · 64 بت · لا يحتاج صلاحيات المسؤول",
"Free for 7 days":"مجانًا لمدة 7 أيام",
"Download and try it free.":"حمّل وجرّب مجانًا.",
"Install 91 TV, add your provider and use everything for 7 days. No code, no card. Love it? Pick a plan any time.":"ثبّت 91 TV، وأضف مزوّدك، واستخدم كل شيء لمدة 7 أيام. بدون رمز وبدون بطاقة. أعجبك؟ اختر خطة في أي وقت.",
"Android TV & Google TV":"Android TV وGoogle TV",
"Sony, TCL, Skyworth, Hisense, Philips, Chromecast with Google TV":"Sony وTCL وSkyworth وHisense وPhilips وChromecast with Google TV",
"On your TV, install the free Downloader app from the Play Store.":"على تلفازك، ثبّت تطبيق <b>Downloader</b> المجاني من متجر Play.",
"Open Downloader and enter this code:":"افتح Downloader وأدخل هذا الرمز:",
"Install, open 91 TV and choose Start 7-day free trial .":"ثبّت التطبيق وافتح 91 TV واختر <b>Start 7-day free trial</b> (بدء التجربة المجانية لمدة 7 أيام).",
"Windows 10 & 11":"Windows 10 و11",
"64-bit · no admin rights needed · about 95 MB":"64 بت · بدون صلاحيات المسؤول · حوالي 95 ميغابايت",
"Download 91 TV and unzip it.":"حمّل 91 TV وفك ضغطه.",
"Open 91TV.exe . If Windows SmartScreen appears, click More info › Run anyway .":"افتح <b>91TV.exe</b>. إذا ظهرت رسالة Windows SmartScreen فاضغط <b>More info › Run anyway</b>.",
"Choose Start 7-day free trial .":"اختر <b>Start 7-day free trial</b>.",
"Download for Windows":"حمّل لـ Windows",
"One app. Three simple plans.":"تطبيق واحد. ثلاث خطط بسيطة.",
"Every plan starts with a 7-day free trial in the app. The same plans for Android TV and Windows, and every code works on 2 devices.":"تبدأ كل خطة بتجربة مجانية لمدة 7 أيام داخل التطبيق. الخطط نفسها لـ Android TV وWindows، وكل رمز يعمل على جهازين.",
"1 Month":"شهر واحد","BHD / month":"د.ب / شهريًا","about US$4 · cancel anytime":"حوالي 4 دولارات · إلغاء في أي وقت",
"All features":"كل المزايا","2 devices":"جهازان","Free updates":"تحديثات مجانية","All future updates":"كل التحديثات المستقبلية",
"Choose monthly":"اختر الشهري","Best value":"أفضل قيمة",
"1 Year":"سنة واحدة","BHD / year":"د.ب / سنويًا","about US$20 · 7 months free":"حوالي 20 دولارًا · 7 أشهر مجانًا","Choose yearly":"اختر السنوي",
"Lifetime":"مدى الحياة","BHD once":"د.ب مرة واحدة","about US$40 · pay once":"حوالي 40 دولارًا · ادفع مرة واحدة","Choose lifetime":"اختر مدى الحياة",
"Secure checkout by Lemon Squeezy · Card, Apple Pay, Google Pay or PayPal · Your code arrives by email instantly":"دفع آمن عبر Lemon Squeezy · بطاقة أو Apple Pay أو Google Pay أو PayPal · يصلك رمزك بالبريد فورًا",
"Getting started":"البدء",
"From download to watching.":"من التحميل إلى المشاهدة.",
"Try it free":"جرّبه مجانًا",
"Download 91 TV and start the 7-day free trial. Everything works, no code or card needed.":"حمّل 91 TV وابدأ التجربة المجانية لمدة 7 أيام. كل شيء يعمل، بدون رمز أو بطاقة.",
"Add your provider":"أضف مزوّدك",
"Enter your M3U link or Xtream login. Your home screen, guide and library fill in by themselves.":"أدخل رابط M3U أو بيانات Xtream. تمتلئ شاشتك الرئيسية والدليل والمكتبة تلقائيًا.",
"Choose a plan":"اختر خطة",
"Pick 1 month, 1 year or lifetime. Your code arrives by email instantly; paste it in and keep watching.":"اختر شهرًا أو سنة أو مدى الحياة. يصلك رمزك بالبريد فورًا؛ الصقه وواصل المشاهدة.",
"91 TV is a player only. It does not provide, sell or include any channels, playlists, movies or other content. You need your own subscription from an IPTV provider you are legally entitled to use. Pictures on this page use original illustrations and sample names.":"<b>91 TV مشغّل فقط.</b> لا يقدّم أو يبيع أو يتضمن أي قنوات أو قوائم تشغيل أو أفلام أو محتوى آخر. تحتاج إلى اشتراكك الخاص من مزوّد IPTV يحق لك استخدامه قانونيًا. الصور في هذه الصفحة رسوم أصلية بأسماء تجريبية.",
"Questions":"الأسئلة","Good to know.":"من المفيد أن تعرف.",
"Is there a free trial?":"هل توجد تجربة مجانية؟",
"Yes. Every new install gets 7 days free with all features. No code and no card needed. When it ends, choose a plan to keep watching.":"نعم. كل تثبيت جديد يحصل على 7 أيام مجانًا بكل المزايا. بدون رمز وبدون بطاقة. عند انتهائها، اختر خطة لتواصل المشاهدة.",
"Do you include channels or a subscription?":"هل تقدمون قنوات أو اشتراكًا؟",
"No. 91 TV is the player app only. You bring your own IPTV provider and add it with an M3U link or an Xtream Codes login.":"لا. 91 TV تطبيق مشغّل فقط. تأتي بمزوّد IPTV الخاص بك وتضيفه برابط M3U أو ببيانات Xtream Codes.",
"Which devices does it work on?":"على أي الأجهزة يعمل؟",
"Android TV and Google TV devices (Sony, TCL, Skyworth, Hisense, Philips, Chromecast with Google TV and more) and Windows 10 / 11 PCs. There are separate plans for TV and Windows.":"أجهزة Android TV وGoogle TV (Sony وTCL وSkyworth وHisense وPhilips وChromecast with Google TV وغيرها) وحواسيب Windows 10 / 11. توجد خطط منفصلة للتلفاز ولـ Windows.",
"How many devices can I use one code on?":"على كم جهاز يعمل الرمز الواحد؟",
"Two. If you change TV or PC, open Settings › Licence on the old one and remove it, then activate the same code on the new one.":"جهازان. إذا غيّرت التلفاز أو الحاسوب، افتح Settings › Licence على الجهاز القديم واحذفه، ثم فعّل الرمز نفسه على الجديد.",
"Does it work without internet?":"هل يعمل بدون إنترنت؟",
"Streaming needs internet, of course. The licence itself keeps working for 7 days without a connection.":"البث يحتاج إلى الإنترنت بالطبع. أما الترخيص فيبقى يعمل 7 أيام بدون اتصال.",
"Can I cancel?":"هل يمكنني الإلغاء؟",
"Yes. Monthly and yearly plans can be cancelled anytime from the link in your receipt email; you keep access until the end of the period you paid for.":"نعم. يمكن إلغاء الخطط الشهرية والسنوية في أي وقت من الرابط في بريد الإيصال؛ ويبقى وصولك حتى نهاية الفترة التي دفعتها.",
"How do I get help?":"كيف أحصل على مساعدة؟",
"Reply to your 91 TV receipt email and we'll help you with installing, activating or moving your licence.":"ردّ على بريد إيصال 91 TV وسنساعدك في التثبيت أو التفعيل أو نقل الترخيص.",
"Ready when you are.":"جاهزون متى كنت جاهزًا.",
"Bring your IPTV subscription. We'll bring the cinema.":"أحضر اشتراك IPTV الخاص بك، ونحن نحضر السينما.",
"© 2026 91 TV · Payments by Lemon Squeezy, our merchant of record.":'© <span id="yr">2026</span> 91 TV · المدفوعات عبر Lemon Squeezy، التاجر المسجّل لدينا.',
"Terms":"الشروط","Privacy":"الخصوصية","Refunds":"الاسترداد",
}

NOTE = "هذه ترجمة للتسهيل. عند أي اختلاف تسود النسخة الإنجليزية."
LEGAL = {
"Terms of use":"شروط الاستخدام","Privacy":"الخصوصية","Refunds":"الاسترداد","Last updated: 31 October 2026":"آخر تحديث: 31 أكتوبر 2026",
"What 91 TV is":"ما هو 91 TV",
"91 TV is a media player for Android TV and Windows. It does not provide, host, sell or include any channels, playlists, movies, series or other content. You connect your own IPTV subscription, and you are responsible for being legally entitled to use it.":"91 TV مشغّل وسائط لأجهزة Android TV وWindows. لا يقدّم أو يستضيف أو يبيع أو يتضمن أي قنوات أو قوائم تشغيل أو أفلام أو مسلسلات أو محتوى آخر. أنت تربط اشتراك IPTV الخاص بك، وأنت المسؤول عن أحقيتك القانونية في استخدامه.",
"Free trial":"التجربة المجانية",
"Every new installation includes a 7-day free trial with all features. No card is needed. When the trial ends you need a plan to keep using the app.":"يتضمن كل تثبيت جديد تجربة مجانية لمدة 7 أيام بكل المزايا. لا حاجة إلى بطاقة. عند انتهاء التجربة تحتاج إلى خطة لمواصلة استخدام التطبيق.",
"Plans and licence":"الخطط والترخيص",
"A plan gives you a personal activation code for 91 TV. One code works on up to 2 of your own devices. Monthly and yearly plans renew until cancelled; a lifetime plan is a single payment. You may not resell, share or publish your code, or copy, modify, decompile or resell the app.":"تمنحك الخطة رمز تفعيل شخصيًا لـ 91 TV. يعمل الرمز الواحد على جهازين من أجهزتك كحد أقصى. تتجدد الخطط الشهرية والسنوية حتى تُلغى؛ أما خطة مدى الحياة فهي دفعة واحدة. لا يجوز لك إعادة بيع الرمز أو مشاركته أو نشره، ولا نسخ التطبيق أو تعديله أو فك تجميعه أو إعادة بيعه.",
"Payments":"المدفوعات",
"Payments are processed by Lemon Squeezy, which is the merchant of record and sells the licence to you. Prices are shown in Bahraini dinar and converted to your currency at checkout.":"تتم معالجة المدفوعات عبر Lemon Squeezy، وهي التاجر المسجّل التي تبيعك الترخيص. تُعرض الأسعار بالدينار البحريني وتُحوّل إلى عملتك عند الدفع.",
"Cancelling":"الإلغاء",
"Monthly and yearly plans can be cancelled at any time from the link in your receipt email. You keep access until the end of the period you paid for.":"يمكن إلغاء الخطط الشهرية والسنوية في أي وقت من الرابط في بريد الإيصال. يبقى وصولك حتى نهاية الفترة التي دفعتها.",
"No warranty":"عدم وجود ضمان",
"91 TV is provided as it is. We cannot promise that it works with every provider or device, or without interruption. Your IPTV service is provided by a third party and we are not responsible for its content or availability.":"يُقدَّم 91 TV كما هو. لا نستطيع أن نعد بأنه يعمل مع كل مزوّد أو جهاز، أو بدون انقطاع. خدمة IPTV الخاصة بك يقدمها طرف ثالث ولسنا مسؤولين عن محتواها أو توفرها.",
"Contact":"التواصل","For help, reply to your 91 TV receipt email.":"للمساعدة، ردّ على بريد إيصال 91 TV.",
"What stays on your device":"ما يبقى على جهازك",
"Your IPTV server address, username and password, your lists and what you have watched stay on your own device. We do not receive them.":"عنوان خادم IPTV واسم المستخدم وكلمة المرور وقوائمك وما شاهدته تبقى كلها على جهازك. نحن لا نستلمها.",
"What is checked online":"ما يُفحص عبر الإنترنت",
"To start the free trial and to check your activation code, the app contacts our licence service with your code and a device name. Prayer times are requested from a public prayer-times service for your city. If you add an OMDb key, ratings are requested from that service.":"لبدء التجربة المجانية وللتحقق من رمز التفعيل، يتصل التطبيق بخدمة الترخيص لدينا مع رمزك واسم الجهاز. تُطلب أوقات الصلاة من خدمة عامة لأوقات الصلاة لمدينتك. وإذا أضفت مفتاح OMDb فتُطلب التقييمات من تلك الخدمة.",
"Payments are handled by Lemon Squeezy. We never see your card details. Lemon Squeezy shares your name and email with us only so that we can support your order.":"تتولى Lemon Squeezy المدفوعات. نحن لا نرى بيانات بطاقتك أبدًا. وتشارك Lemon Squeezy اسمك وبريدك معنا فقط لنتمكن من دعم طلبك.",
"Selling or sharing":"البيع أو المشاركة",
"We do not sell your information and we do not show ads.":"نحن لا نبيع معلوماتك ولا نعرض إعلانات.",
"Your choices":"خياراتك",
"You can delete the app at any time, which removes everything stored on your device. To ask about information held for your order, reply to your receipt email.":"يمكنك حذف التطبيق في أي وقت، وبذلك يُزال كل ما هو مخزّن على جهازك. للاستفسار عن المعلومات المحفوظة لطلبك، ردّ على بريد الإيصال.",
"Try before you pay":"جرّب قبل أن تدفع",
"Every installation starts with a 7-day free trial, so you can check that 91 TV works with your provider and your device before you buy.":"يبدأ كل تثبيت بتجربة مجانية لمدة 7 أيام، لتتأكد أن 91 TV يعمل مع مزوّدك وجهازك قبل الشراء.",
"If it does not work for you":"إذا لم يناسبك",
"If you buy a plan and 91 TV does not work for you, reply to your receipt email within 14 days of purchase and we will refund you.":"إذا اشتريت خطة ولم يعمل 91 TV معك، فردّ على بريد الإيصال خلال 14 يومًا من الشراء وسنعيد إليك المبلغ.",
"Subscriptions":"الاشتراكات",
"Monthly and yearly plans can be cancelled at any time. Cancelling stops the next renewal; you keep access until the end of the period you already paid for.":"يمكن إلغاء الخطط الشهرية والسنوية في أي وقت. يوقف الإلغاء التجديد القادم؛ ويبقى وصولك حتى نهاية الفترة التي دفعتها.",
"How refunds are paid":"كيف يُدفع الاسترداد",
"Refunds go back to the original payment method through Lemon Squeezy and usually appear within a few days.":"يعود المبلغ المسترد إلى وسيلة الدفع الأصلية عبر Lemon Squeezy، ويظهر عادةً خلال بضعة أيام.",
"Home":"الرئيسية","© 2026 91 TV":"© 2026 91 TV",
}

LAT=re.compile(r"[A-Za-z0-9][A-Za-z0-9 .,&/'%+\-–›·:]*[A-Za-z0-9.%+)]|[A-Za-z0-9]")
def iso(v):
    parts=re.split(r"(<[^>]+>)",v)
    return re.sub(r"و<bdi>","و <bdi>","".join(x if x.startswith("<") else LAT.sub(lambda m:"<bdi>"+m.group(0)+"</bdi>",x) for x in parts))

def norm(el): return " ".join(el.get_text(" ").split())

def process(path, table, legal=False):
    soup = BeautifulSoup(open(path, encoding="utf-8").read(), "html.parser")
    for el in soup.find_all(attrs={"data-ar": True}): del el["data-ar"]
    for b in soup.find_all(id="lang"): b.decompose()
    for s in soup.find_all("script", src=re.compile(r"i18n\.js")): s.decompose()
    for el in soup.find_all(attrs={"data-arnote": True}): el.decompose()
    done = 0
    def walk(node):
        nonlocal done
        for ch in list(getattr(node, "children", [])):
            if getattr(ch, "name", None) in (None, "script", "style", "head", "svg"): continue
            t = norm(ch)
            if t in table and ch.name not in ("html", "body", "main", "section", "header", "footer", "nav", "ul", "div") or (t in table and ch.name == "div" and not ch.find(["p", "h1", "h2", "h3", "li", "div"])):
                ch["data-ar"] = iso(table[t]); done += 1
            else:
                walk(ch)
    walk(soup.body)
    # language button
    btn = soup.new_tag("button", id="lang", type="button"); btn.string = "العربية"; btn["aria-label"] = "Switch language"
    if legal:
        hd = soup.find("header"); hd.append(btn)
        h1 = soup.find("h1"); note = soup.new_tag("p", attrs={"class": "d", "data-arnote": "1", "hidden": ""}); note.string = NOTE; h1.insert_after(note)
        note["id"] = "arnote"
    else:
        soup.select_one(".nav .wrap a.btn").insert_before(btn)
    sc = soup.new_tag("script", src=("site/i18n.js")); sc["defer"] = ""; soup.body.append(sc)
    open(path, "w", encoding="utf-8").write(str(soup))
    return done

if __name__ == "__main__":
    print("index", process("docs/index.html", MAIN))
    for p in ("terms", "privacy", "refund"): print(p, process(f"docs/{p}.html", LEGAL, legal=True))
