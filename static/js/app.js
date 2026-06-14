const form = document.querySelector("#chat-form");
const input = document.querySelector("#message-input");
const sendButton = document.querySelector("#send-button");
const messages = document.querySelector("#messages");
const statusEl = document.querySelector("#status");
const clearButton = document.querySelector("#clear-button");
const SUGGESTION_LIMIT = 2;
const RTL_LANGUAGES = new Set(["ar", "ur"]);
const FOLLOWUP_TEXT = {
  en: {
    label: "You might also want to ask:",
    defaults: [
      "What are breathing exercises for anxiety?",
      "When should I see a therapist?",
    ],
    topics: {
      crisis: [
        "Who can I contact right now for crisis support?",
        "How can I make a safety plan for tonight?",
      ],
      anxiety: [
        "What are breathing exercises for anxiety?",
        "How does CBT help with anxiety?",
      ],
      panic: [
        "What can I do during a panic attack?",
        "How can I calm my body quickly?",
      ],
      sleep: [
        "What can I try tonight if I cannot sleep?",
        "How can anxiety affect sleep?",
      ],
      lowMood: [
        "What small steps can help when I feel low?",
        "When should I see a therapist?",
      ],
    },
  },
  ar: {
    label: "قد ترغب أيضا في السؤال:",
    defaults: ["ما تمارين التنفس للقلق؟", "متى يجب أن أرى معالجا؟"],
    topics: {
      crisis: ["بمن يمكنني التواصل الآن لدعم الأزمات؟", "كيف أضع خطة أمان لهذه الليلة؟"],
      anxiety: ["ما تمارين التنفس للقلق؟", "كيف يساعد العلاج المعرفي السلوكي في القلق؟"],
      panic: ["ماذا أفعل أثناء نوبة الهلع؟", "كيف أهدئ جسمي بسرعة؟"],
      sleep: ["ماذا أجرب الليلة إذا لم أستطع النوم؟", "كيف يمكن أن يؤثر القلق على النوم؟"],
      lowMood: ["ما الخطوات الصغيرة التي تساعد عندما أشعر بالإحباط؟", "متى يجب أن أرى معالجا؟"],
    },
  },
  es: {
    label: "También podrías preguntar:",
    defaults: ["¿Qué ejercicios de respiración ayudan con la ansiedad?", "¿Cuándo debería ver a un terapeuta?"],
    topics: {
      crisis: ["¿Con quién puedo contactar ahora para apoyo en crisis?", "¿Cómo puedo hacer un plan de seguridad para esta noche?"],
      anxiety: ["¿Qué ejercicios de respiración ayudan con la ansiedad?", "¿Cómo ayuda la TCC con la ansiedad?"],
      panic: ["¿Qué puedo hacer durante un ataque de pánico?", "¿Cómo puedo calmar mi cuerpo rápidamente?"],
      sleep: ["¿Qué puedo probar esta noche si no puedo dormir?", "¿Cómo puede afectar la ansiedad al sueño?"],
      lowMood: ["¿Qué pequeños pasos ayudan cuando me siento bajo de ánimo?", "¿Cuándo debería ver a un terapeuta?"],
    },
  },
  fr: {
    label: "Vous pourriez aussi demander :",
    defaults: ["Quels exercices de respiration aident contre l'anxiété ?", "Quand devrais-je consulter un thérapeute ?"],
    topics: {
      crisis: ["Qui puis-je contacter maintenant pour un soutien de crise ?", "Comment créer un plan de sécurité pour ce soir ?"],
      anxiety: ["Quels exercices de respiration aident contre l'anxiété ?", "Comment la TCC aide-t-elle contre l'anxiété ?"],
      panic: ["Que puis-je faire pendant une crise de panique ?", "Comment calmer rapidement mon corps ?"],
      sleep: ["Que puis-je essayer ce soir si je n'arrive pas à dormir ?", "Comment l'anxiété peut-elle affecter le sommeil ?"],
      lowMood: ["Quelles petites étapes peuvent aider quand je me sens mal ?", "Quand devrais-je consulter un thérapeute ?"],
    },
  },
  hi: {
    label: "आप यह भी पूछना चाह सकते हैं:",
    defaults: ["चिंता के लिए कौन से सांस लेने के अभ्यास मदद कर सकते हैं?", "मुझे थेरेपिस्ट से कब मिलना चाहिए?"],
    topics: {
      crisis: ["अभी संकट सहायता के लिए मैं किससे संपर्क कर सकता हूं?", "आज रात के लिए मैं सुरक्षा योजना कैसे बना सकता हूं?"],
      anxiety: ["चिंता के लिए कौन से सांस लेने के अभ्यास मदद कर सकते हैं?", "सीबीटी चिंता में कैसे मदद करता है?"],
      panic: ["पैनिक अटैक के दौरान मैं क्या कर सकता हूं?", "मैं अपने शरीर को जल्दी कैसे शांत कर सकता हूं?"],
      sleep: ["अगर मुझे नींद नहीं आ रही है तो आज रात क्या आजमा सकता हूं?", "चिंता नींद को कैसे प्रभावित कर सकती है?"],
      lowMood: ["जब मेरा मन बहुत उदास हो तो कौन से छोटे कदम मदद कर सकते हैं?", "मुझे थेरेपिस्ट से कब मिलना चाहिए?"],
    },
  },
  zh: {
    label: "你也可以问：",
    defaults: ["哪些呼吸练习可以缓解焦虑？", "我什么时候应该看心理治疗师？"],
    topics: {
      crisis: ["我现在可以联系谁获得危机支持？", "今晚我该如何制定安全计划？"],
      anxiety: ["哪些呼吸练习可以缓解焦虑？", "认知行为疗法如何帮助焦虑？"],
      panic: ["惊恐发作时我可以做什么？", "我怎样才能快速让身体平静下来？"],
      sleep: ["如果今晚睡不着，我可以尝试什么？", "焦虑会如何影响睡眠？"],
      lowMood: ["情绪低落时哪些小步骤会有帮助？", "我什么时候应该看心理治疗师？"],
    },
  },
  de: {
    label: "Du könntest auch fragen:",
    defaults: ["Welche Atemübungen helfen bei Angst?", "Wann sollte ich eine Therapeutin oder einen Therapeuten aufsuchen?"],
    topics: {
      crisis: ["An wen kann ich mich jetzt für Krisenhilfe wenden?", "Wie erstelle ich für heute Abend einen Sicherheitsplan?"],
      anxiety: ["Welche Atemübungen helfen bei Angst?", "Wie hilft CBT bei Angst?"],
      panic: ["Was kann ich während einer Panikattacke tun?", "Wie kann ich meinen Körper schnell beruhigen?"],
      sleep: ["Was kann ich heute Abend versuchen, wenn ich nicht schlafen kann?", "Wie kann Angst den Schlaf beeinflussen?"],
      lowMood: ["Welche kleinen Schritte helfen, wenn ich mich niedergeschlagen fühle?", "Wann sollte ich eine Therapeutin oder einen Therapeuten aufsuchen?"],
    },
  },
  it: {
    label: "Potresti anche chiedere:",
    defaults: ["Quali esercizi di respirazione aiutano con l'ansia?", "Quando dovrei vedere un terapeuta?"],
    topics: {
      crisis: ["Chi posso contattare subito per supporto in crisi?", "Come posso creare un piano di sicurezza per stasera?"],
      anxiety: ["Quali esercizi di respirazione aiutano con l'ansia?", "Come aiuta la CBT con l'ansia?"],
      panic: ["Cosa posso fare durante un attacco di panico?", "Come posso calmare rapidamente il corpo?"],
      sleep: ["Cosa posso provare stasera se non riesco a dormire?", "In che modo l'ansia può influenzare il sonno?"],
      lowMood: ["Quali piccoli passi aiutano quando mi sento giù?", "Quando dovrei vedere un terapeuta?"],
    },
  },
  pt: {
    label: "Você também pode perguntar:",
    defaults: ["Quais exercícios de respiração ajudam na ansiedade?", "Quando devo procurar um terapeuta?"],
    topics: {
      crisis: ["Com quem posso falar agora para apoio em crise?", "Como posso criar um plano de segurança para esta noite?"],
      anxiety: ["Quais exercícios de respiração ajudam na ansiedade?", "Como a TCC ajuda na ansiedade?"],
      panic: ["O que posso fazer durante um ataque de pânico?", "Como posso acalmar meu corpo rapidamente?"],
      sleep: ["O que posso tentar hoje à noite se não conseguir dormir?", "Como a ansiedade pode afetar o sono?"],
      lowMood: ["Que pequenos passos ajudam quando me sinto para baixo?", "Quando devo procurar um terapeuta?"],
    },
  },
  ru: {
    label: "Вы также можете спросить:",
    defaults: ["Какие дыхательные упражнения помогают при тревоге?", "Когда стоит обратиться к терапевту?"],
    topics: {
      crisis: ["К кому я могу обратиться прямо сейчас за кризисной поддержкой?", "Как составить план безопасности на сегодня?"],
      anxiety: ["Какие дыхательные упражнения помогают при тревоге?", "Как КПТ помогает при тревоге?"],
      panic: ["Что можно сделать во время панической атаки?", "Как быстро успокоить тело?"],
      sleep: ["Что попробовать сегодня вечером, если я не могу уснуть?", "Как тревога влияет на сон?"],
      lowMood: ["Какие маленькие шаги помогают, когда мне плохо?", "Когда стоит обратиться к терапевту?"],
    },
  },
  tr: {
    label: "Şunu da sormak isteyebilirsiniz:",
    defaults: ["Kaygı için hangi nefes egzersizleri yardımcı olur?", "Ne zaman bir terapiste görünmeliyim?"],
    topics: {
      crisis: ["Kriz desteği için şimdi kiminle iletişime geçebilirim?", "Bu gece için nasıl bir güvenlik planı yapabilirim?"],
      anxiety: ["Kaygı için hangi nefes egzersizleri yardımcı olur?", "BDT kaygıya nasıl yardımcı olur?"],
      panic: ["Panik atak sırasında ne yapabilirim?", "Bedenimi hızlıca nasıl sakinleştirebilirim?"],
      sleep: ["Uyuyamıyorsam bu gece ne deneyebilirim?", "Kaygı uykuyu nasıl etkileyebilir?"],
      lowMood: ["Kendimi kötü hissettiğimde hangi küçük adımlar yardımcı olur?", "Ne zaman bir terapiste görünmeliyim?"],
    },
  },
  ur: {
    label: "آپ یہ بھی پوچھ سکتے ہیں:",
    defaults: ["بے چینی کے لیے کون سی سانس کی مشقیں مدد کر سکتی ہیں؟", "مجھے کب کسی تھراپسٹ سے ملنا چاہیے؟"],
    topics: {
      crisis: ["میں ابھی بحران میں مدد کے لیے کس سے رابطہ کر سکتا ہوں؟", "آج رات کے لیے حفاظتی منصوبہ کیسے بنا سکتا ہوں؟"],
      anxiety: ["بے چینی کے لیے کون سی سانس کی مشقیں مدد کر سکتی ہیں؟", "سی بی ٹی بے چینی میں کیسے مدد کرتی ہے؟"],
      panic: ["پینک اٹیک کے دوران میں کیا کر سکتا ہوں؟", "میں اپنے جسم کو جلدی کیسے پرسکون کر سکتا ہوں؟"],
      sleep: ["اگر مجھے نیند نہیں آ رہی تو آج رات کیا آزما سکتا ہوں؟", "بے چینی نیند کو کیسے متاثر کر سکتی ہے؟"],
      lowMood: ["جب میرا موڈ بہت خراب ہو تو کون سے چھوٹے قدم مدد کر سکتے ہیں؟", "مجھے کب کسی تھراپسٹ سے ملنا چاہیے؟"],
    },
  },
  ja: {
    label: "次にこんな質問もできます:",
    defaults: ["不安に役立つ呼吸法は何ですか？", "いつセラピストに相談すべきですか？"],
    topics: {
      crisis: ["今すぐ危機支援を受けるには誰に連絡できますか？", "今夜の安全計画はどう作れますか？"],
      anxiety: ["不安に役立つ呼吸法は何ですか？", "CBTは不安にどう役立ちますか？"],
      panic: ["パニック発作の時に何ができますか？", "体をすばやく落ち着かせるには？"],
      sleep: ["眠れない夜に試せることは何ですか？", "不安は睡眠にどう影響しますか？"],
      lowMood: ["気分が落ち込む時に役立つ小さな一歩は？", "いつセラピストに相談すべきですか？"],
    },
  },
  nl: {
    label: "Je kunt ook vragen:",
    defaults: ["Welke ademhalingsoefeningen helpen bij angst?", "Wanneer moet ik een therapeut spreken?"],
    topics: {
      crisis: ["Met wie kan ik nu contact opnemen voor crisishulp?", "Hoe maak ik een veiligheidsplan voor vanavond?"],
      anxiety: ["Welke ademhalingsoefeningen helpen bij angst?", "Hoe helpt CGT bij angst?"],
      panic: ["Wat kan ik doen tijdens een paniekaanval?", "Hoe kan ik mijn lichaam snel kalmeren?"],
      sleep: ["Wat kan ik vanavond proberen als ik niet kan slapen?", "Hoe kan angst slaap beïnvloeden?"],
      lowMood: ["Welke kleine stappen helpen als ik me somber voel?", "Wanneer moet ik een therapeut spreken?"],
    },
  },
  pl: {
    label: "Możesz też zapytać:",
    defaults: ["Jakie ćwiczenia oddechowe pomagają przy lęku?", "Kiedy warto zgłosić się do terapeuty?"],
    topics: {
      crisis: ["Z kim mogę skontaktować się teraz po wsparcie kryzysowe?", "Jak mogę stworzyć plan bezpieczeństwa na dzisiejszy wieczór?"],
      anxiety: ["Jakie ćwiczenia oddechowe pomagają przy lęku?", "Jak CBT pomaga przy lęku?"],
      panic: ["Co mogę zrobić podczas ataku paniki?", "Jak szybko uspokoić ciało?"],
      sleep: ["Co mogę spróbować dziś wieczorem, jeśli nie mogę spać?", "Jak lęk może wpływać na sen?"],
      lowMood: ["Jakie małe kroki pomagają, gdy czuję się źle?", "Kiedy warto zgłosić się do terapeuty?"],
    },
  },
  bg: {
    label: "Може също да попитате:",
    defaults: ["Кои дихателни упражнения помагат при тревожност?", "Кога трябва да посетя терапевт?"],
    topics: {
      crisis: ["С кого мога да се свържа сега за кризисна подкрепа?", "Как да направя план за безопасност за тази вечер?"],
      anxiety: ["Кои дихателни упражнения помагат при тревожност?", "Как CBT помага при тревожност?"],
      panic: ["Какво мога да направя по време на паник атака?", "Как бързо да успокоя тялото си?"],
      sleep: ["Какво мога да опитам тази вечер, ако не мога да спя?", "Как тревожността може да влияе на съня?"],
      lowMood: ["Кои малки стъпки помагат, когато се чувствам зле?", "Кога трябва да посетя терапевт?"],
    },
  },
  el: {
    label: "Μπορείτε επίσης να ρωτήσετε:",
    defaults: ["Ποιες ασκήσεις αναπνοής βοηθούν στο άγχος;", "Πότε πρέπει να δω θεραπευτή;"],
    topics: {
      crisis: ["Με ποιον μπορώ να επικοινωνήσω τώρα για υποστήριξη σε κρίση;", "Πώς μπορώ να φτιάξω ένα σχέδιο ασφάλειας για απόψε;"],
      anxiety: ["Ποιες ασκήσεις αναπνοής βοηθούν στο άγχος;", "Πώς βοηθά η CBT στο άγχος;"],
      panic: ["Τι μπορώ να κάνω κατά τη διάρκεια μιας κρίσης πανικού;", "Πώς μπορώ να ηρεμήσω γρήγορα το σώμα μου;"],
      sleep: ["Τι μπορώ να δοκιμάσω απόψε αν δεν μπορώ να κοιμηθώ;", "Πώς μπορεί το άγχος να επηρεάσει τον ύπνο;"],
      lowMood: ["Ποια μικρά βήματα βοηθούν όταν νιώθω πεσμένος;", "Πότε πρέπει να δω θεραπευτή;"],
    },
  },
  sw: {
    label: "Unaweza pia kuuliza:",
    defaults: ["Mazoezi gani ya kupumua husaidia wasiwasi?", "Ni lini ninapaswa kumuona mtaalamu wa tiba?"],
    topics: {
      crisis: ["Ninaweza kuwasiliana na nani sasa kwa msaada wa dharura?", "Ninawezaje kutengeneza mpango wa usalama kwa usiku wa leo?"],
      anxiety: ["Mazoezi gani ya kupumua husaidia wasiwasi?", "CBT husaidiaje kwenye wasiwasi?"],
      panic: ["Nifanye nini wakati wa shambulio la hofu?", "Ninawezaje kuituliza mwili wangu haraka?"],
      sleep: ["Ninaweza kujaribu nini usiku huu kama siwezi kulala?", "Wasiwasi unaweza kuathirije usingizi?"],
      lowMood: ["Hatua gani ndogo husaidia ninapojisikia vibaya?", "Ni lini ninapaswa kumuona mtaalamu wa tiba?"],
    },
  },
  th: {
    label: "คุณอาจอยากถามเพิ่มเติมว่า:",
    defaults: ["แบบฝึกหายใจใดช่วยเรื่องความวิตกกังวลได้?", "ฉันควรพบผู้บำบัดเมื่อไร?"],
    topics: {
      crisis: ["ฉันสามารถติดต่อใครตอนนี้เพื่อรับความช่วยเหลือในภาวะวิกฤต?", "ฉันจะทำแผนความปลอดภัยสำหรับคืนนี้ได้อย่างไร?"],
      anxiety: ["แบบฝึกหายใจใดช่วยเรื่องความวิตกกังวลได้?", "CBT ช่วยเรื่องความวิตกกังวลได้อย่างไร?"],
      panic: ["ฉันทำอะไรได้บ้างระหว่างอาการแพนิก?", "ฉันจะทำให้ร่างกายสงบลงเร็ว ๆ ได้อย่างไร?"],
      sleep: ["คืนนี้ถ้านอนไม่หลับ ฉันลองทำอะไรได้บ้าง?", "ความวิตกกังวลส่งผลต่อการนอนอย่างไร?"],
      lowMood: ["เมื่อรู้สึกแย่ ขั้นตอนเล็ก ๆ อะไรช่วยได้บ้าง?", "ฉันควรพบผู้บำบัดเมื่อไร?"],
    },
  },
  vi: {
    label: "Bạn cũng có thể hỏi:",
    defaults: ["Bài tập thở nào giúp giảm lo âu?", "Khi nào tôi nên gặp nhà trị liệu?"],
    topics: {
      crisis: ["Tôi có thể liên hệ với ai ngay bây giờ để được hỗ trợ khủng hoảng?", "Làm sao để lập kế hoạch an toàn cho tối nay?"],
      anxiety: ["Bài tập thở nào giúp giảm lo âu?", "CBT giúp ích thế nào cho lo âu?"],
      panic: ["Tôi có thể làm gì trong cơn hoảng loạn?", "Làm sao để cơ thể bình tĩnh nhanh hơn?"],
      sleep: ["Tối nay tôi có thể thử gì nếu không ngủ được?", "Lo âu có thể ảnh hưởng đến giấc ngủ thế nào?"],
      lowMood: ["Những bước nhỏ nào giúp khi tôi thấy buồn chán?", "Khi nào tôi nên gặp nhà trị liệu?"],
    },
  },
};

let sessionId = localStorage.getItem("mento_session_id") || crypto.randomUUID();
localStorage.setItem("mento_session_id", sessionId);
let lastMentalHealthTopic = localStorage.getItem("mento_last_mental_health_topic") || "";
let activeChatController = null;
let statusResetTimer = null;

function addMessage(role, text = "") {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  article.appendChild(bubble);
  messages.appendChild(article);
  messages.scrollTop = messages.scrollHeight;
  return { article, bubble };
}

function addAssistantResponse(query) {
  const message = addMessage("assistant", "");
  return {
    article: message.article,
    bubble: message.bubble,
    query,
    responseText: "",
    translatedQuery: "",
    language: "en",
    finalized: false,
    feedbackSent: false,
    isError: false,
  };
}

function setBusy(isBusy) {
  window.clearTimeout(statusResetTimer);
  sendButton.disabled = isBusy;
  input.disabled = isBusy;
  statusEl.textContent = isBusy ? "Thinking" : "Ready";
}

function setTemporaryStatus(text) {
  window.clearTimeout(statusResetTimer);
  statusEl.textContent = text;
  statusResetTimer = window.setTimeout(() => {
    statusEl.textContent = activeChatController ? "Thinking" : "Ready";
  }, 1600);
}

function resetConversation() {
  sessionId = crypto.randomUUID();
  lastMentalHealthTopic = "";
  localStorage.setItem("mento_session_id", sessionId);
  localStorage.removeItem("mento_last_mental_health_topic");
  input.value = "";
  autoresize();
  messages.innerHTML = "";
  addMessage("assistant", "Hello, I'm Mento. What's on your mind today?");
}

function languageCode(language) {
  const code = String(language || "en").toLowerCase().split("-")[0];
  return FOLLOWUP_TEXT[code] ? code : "en";
}

function followupTopicFor(text) {
  if (
    /suicide|kill myself|end my life|take my life|commit suicide|die by suicide|hurt myself|harm myself|self-harm|can't stay safe|cannot stay safe/.test(
      text
    )
  ) {
    return "crisis";
  }
  if (/panic|panic attack/.test(text)) return "panic";
  if (/sleep|insomnia|can't sleep|cannot sleep|nightmare/.test(text)) return "sleep";
  if (/sad|depress|lonely|alone|low mood|hopeless|grief/.test(text)) return "lowMood";
  if (/anxiety|anxious|worry|worried|stress|stressed|fear/.test(text)) return "anxiety";
  return "defaults";
}

function suggestedQuestionsFor(state) {
  const language = languageCode(state.language);
  const copy = FOLLOWUP_TEXT[language] || FOLLOWUP_TEXT.en;
  const text = `${state.query} ${state.translatedQuery} ${state.responseText}`.toLowerCase();
  const topic = followupTopicFor(text);
  const source = topic === "defaults" ? copy.defaults : copy.topics[topic];
  const suggestions = [];
  const add = (question) => {
    if (!suggestions.includes(question)) suggestions.push(question);
  };

  for (const question of source || []) add(question);
  for (const question of copy.defaults) add(question);
  return {
    label: copy.label,
    questions: suggestions.slice(0, SUGGESTION_LIMIT),
    language,
  };
}

function appendFollowUps(state) {
  if (state.isError) return;

  const suggestions = suggestedQuestionsFor(state);
  if (!suggestions.questions.length) return;

  const followUps = document.createElement("div");
  followUps.className = "followups";
  followUps.dir = RTL_LANGUAGES.has(suggestions.language) ? "rtl" : "ltr";

  const label = document.createElement("span");
  label.className = "followups-label";
  label.textContent = suggestions.label;
  followUps.appendChild(label);

  const list = document.createElement("div");
  list.className = "suggestion-list";
  for (const question of suggestions.questions) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "suggestion-chip";
    button.textContent = question;
    button.addEventListener("click", () => {
      input.value = question;
      autoresize();
      input.focus();
    });
    list.appendChild(button);
  }

  followUps.appendChild(list);
  state.bubble.appendChild(followUps);
}

function appendFeedbackControls(state) {
  if (!state.query || !state.responseText) return;

  const actions = document.createElement("div");
  actions.className = "feedback-actions";

  const label = document.createElement("span");
  label.className = "feedback-label";
  label.textContent = "Was this helpful?";
  actions.appendChild(label);

  const createButton = (feedback, icon, labelText) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "feedback-button";
    button.dataset.feedback = feedback;
    button.textContent = icon;
    button.title = labelText;
    button.setAttribute("aria-label", labelText);
    button.addEventListener("click", () => submitFeedback(state, feedback, actions));
    return button;
  };

  actions.appendChild(createButton("like", "\uD83D\uDC4D", "Like this response"));
  actions.appendChild(createButton("dislike", "\uD83D\uDC4E", "Dislike this response"));

  const feedbackState = document.createElement("span");
  feedbackState.className = "feedback-state";
  feedbackState.setAttribute("aria-live", "polite");
  actions.appendChild(feedbackState);

  state.bubble.appendChild(actions);
}

async function submitFeedback(state, feedback, actions) {
  if (state.feedbackSent) return;

  state.feedbackSent = true;
  const buttons = actions.querySelectorAll("button");
  buttons.forEach((button) => {
    button.disabled = true;
  });
  actions.querySelector(".feedback-state").textContent = "Saving";

  try {
    const feedbackResponse = await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: state.query,
        response: state.responseText,
        feedback,
      }),
    });

    if (!feedbackResponse.ok) {
      const data = await feedbackResponse.json().catch(() => ({}));
      throw new Error(data.message || "Feedback could not be saved.");
    }

    actions.dataset.feedback = feedback;
    const selected = actions.querySelector(`[data-feedback="${feedback}"]`);
    if (selected) selected.classList.add("selected");
    actions.querySelector(".feedback-state").textContent = "Saved";
    setTemporaryStatus("Feedback saved");
  } catch (error) {
    state.feedbackSent = false;
    buttons.forEach((button) => {
      button.disabled = false;
    });
    actions.querySelector(".feedback-state").textContent = "Could not save";
    setTemporaryStatus("Feedback not saved");
  }
}

function finalizeAssistantResponse(state) {
  if (!state || state.finalized) return;

  const responseText = (state.responseText || state.bubble.textContent || "").trim();
  if (!responseText) return;

  state.responseText = responseText;
  state.bubble.textContent = responseText;
  appendFollowUps(state);
  appendFeedbackControls(state);
  state.finalized = true;
  messages.scrollTop = messages.scrollHeight;
}

function updateMetadata(data) {
  return data;
}

async function parseStream(response, assistantState) {
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }
  if (!response.body) {
    throw new Error("The response stream could not be opened.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let currentAssistant = assistantState;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";

    for (const event of events) {
      const line = event.split("\n").find((part) => part.startsWith("data: "));
      if (!line) continue;
      const payload = JSON.parse(line.slice(6));

      if (payload.type === "session") {
        sessionId = payload.session_id;
        localStorage.setItem("mento_session_id", sessionId);
      } else if (payload.type === "metadata") {
        if (payload.data && payload.data.language) {
          currentAssistant.language = payload.data.language;
        }
        if (payload.data && payload.data.translated) {
          currentAssistant.translatedQuery = payload.data.translated;
        }
        updateMetadata(payload.data);
      } else if (payload.type === "token") {
        currentAssistant.responseText += payload.text;
        currentAssistant.bubble.textContent += payload.text;
        messages.scrollTop = messages.scrollHeight;
      } else if (payload.type === "new_assistant_message") {
        finalizeAssistantResponse(currentAssistant);
        const previousLanguage = currentAssistant.language;
        const previousTranslatedQuery = currentAssistant.translatedQuery;
        currentAssistant = addAssistantResponse(assistantState.query);
        currentAssistant.language = previousLanguage;
        currentAssistant.translatedQuery = previousTranslatedQuery;
      } else if (payload.type === "replace") {
        currentAssistant.responseText = payload.text;
        currentAssistant.bubble.textContent = payload.text;
      } else if (payload.type === "notice") {
        statusEl.textContent = "Fallback";
      } else if (payload.type === "error") {
        currentAssistant.isError = true;
        currentAssistant.responseText = payload.message;
        currentAssistant.bubble.textContent = payload.message;
      } else if (payload.type === "done") {
        if (payload.data && payload.data.language) {
          currentAssistant.language = payload.data.language;
        }
        if (payload.data && payload.data.translated) {
          currentAssistant.translatedQuery = payload.data.translated;
        }
        updateMetadata(payload.data);
        if (payload.data && payload.data.mental_health_topic) {
          lastMentalHealthTopic = payload.data.mental_health_topic;
          localStorage.setItem("mento_last_mental_health_topic", lastMentalHealthTopic);
        }
        finalizeAssistantResponse(currentAssistant);
      }
    }
  }

  finalizeAssistantResponse(currentAssistant);
}

function autoresize() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 150)}px`;
}

input.addEventListener("input", autoresize);
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;

  addMessage("user", message);
  input.value = "";
  autoresize();
  const assistantState = addAssistantResponse(message);
  setBusy(true);
  const chatController = new AbortController();
  activeChatController = chatController;

  try {
    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: chatController.signal,
      body: JSON.stringify({
        message,
        session_id: sessionId,
        last_mental_health_topic: lastMentalHealthTopic,
      }),
    });
    await parseStream(response, assistantState);
  } catch (error) {
    if (error.name === "AbortError") return;
    const message = String(error.message || "").toLowerCase();
    assistantState.isError = true;
    assistantState.responseText = message.includes("network") || message.includes("failed to fetch")
      ? "The local Flask connection stopped during this request. Please restart or refresh Mento, then try again."
      : error.message;
    assistantState.bubble.textContent = assistantState.responseText;
    finalizeAssistantResponse(assistantState);
  } finally {
    if (activeChatController === chatController) {
      activeChatController = null;
    }
    setBusy(false);
    input.focus();
  }
});

clearButton.addEventListener("click", async () => {
  const sessionToClear = sessionId;
  if (activeChatController) {
    activeChatController.abort();
    activeChatController = null;
  }
  clearButton.disabled = true;
  statusEl.textContent = "Clearing";

  try {
    await fetch("/api/chat/clear", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionToClear }),
    });
  } finally {
    resetConversation();
    clearButton.disabled = false;
    setBusy(false);
    input.focus();
  }
});
