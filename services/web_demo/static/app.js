const ui = {
  launchScreen: document.querySelector("#launch-screen"),
  launchLockup: document.querySelector("#launch-lockup"),
  brandMark: document.querySelector("#brand-mark"),
  appearanceSelect: document.querySelector("#appearance-select"),
  themeColorMeta: document.querySelector('meta[name="theme-color"]'),
  statusBarMeta: document.querySelector(
    'meta[name="apple-mobile-web-app-status-bar-style"]',
  ),
  workspace: document.querySelector("#workspace"),
  decision: document.querySelector("#decision"),
  primaryActions: document.querySelector("#primary-actions"),
  controls: document.querySelector("#universal-controls"),
  stopSlot: document.querySelector("#stop-slot"),
  status: document.querySelector("#status-message"),
  gate: document.querySelector("#confirm-gate"),
  mode: document.querySelector("#mode-badge"),
  voice: document.querySelector("#voice-status"),
  progressLabel: document.querySelector("#progress-label"),
  progressTrack: document.querySelector("#progress-track"),
  progress: document.querySelector("#progress-value"),
  languageToggle: document.querySelector("#language-toggle"),
  traceButton: document.querySelector("#trace-button"),
  traceDialog: document.querySelector("#trace-dialog"),
  traceClose: document.querySelector("#trace-close"),
  trace: document.querySelector("#trace-list"),
  traceEmpty: document.querySelector("#trace-empty"),
  traceCount: document.querySelector("#trace-count"),
  accessDialog: document.querySelector("#access-dialog"),
  accessForm: document.querySelector("#access-form"),
  accessCode: document.querySelector("#access-code"),
  accessError: document.querySelector("#access-error"),
  profileButton: document.querySelector("#profile-button"),
  profileDialog: document.querySelector("#profile-dialog"),
  profileForm: document.querySelector("#profile-form"),
  profileSelect: document.querySelector("#profile-select"),
  profileInput: document.querySelector("#profile-input"),
  profileError: document.querySelector("#profile-error"),
  editDialog: document.querySelector("#edit-dialog"),
  editForm: document.querySelector("#edit-form"),
  editText: document.querySelector("#edit-text"),
  editError: document.querySelector("#edit-error"),
  editCancel: document.querySelector("#edit-cancel"),
  candidateTemplate: document.querySelector("#candidate-template"),
};

const RECORDING_STOP_HEADROOM_SECONDS = 0.5;
const WAVEFORM_BARS = 20;
const LANGUAGE_KEY = "meantbyme_ui_language";
const APPEARANCE_KEY = "meantbyme_ui_appearance";
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const systemDarkAppearance = window.matchMedia("(prefers-color-scheme: dark)");
// Above this width the trace panel docks beside the phone frame instead of
// sliding up as a modal sheet.
const dockedTrace = window.matchMedia("(min-width: 56.25rem)");

/* ── Interface strings ────────────────────────────────────────────────────────
   UI chrome only. Candidate text, clarification questions and ASR fragments
   come from the runtime in the session's own language.
   ────────────────────────────────────────────────────────────────────────── */

const strings = {
  en: {
    htmlLang: "en",
    otherLanguageLabel: "中",
    languageToggleTitle: "Switch interface language",
    languageToggleAria: "Switch interface language to Chinese",
    appearanceLabel: "Appearance",
    appearanceAuto: "Auto",
    appearanceLight: "Light",
    appearanceDark: "Dark",
    skipLink: "Skip to current decision",
    brandName: "MeantByMe",
    brandTagline: "Completed with AI. Meant by me.",
    simulationNotice: "Simulated data. Not a clinical accuracy claim.",
    noProfile: "No profile",
    noProfileControl: "No profile (control)",
    profileButtonTitle: "Choose simulated profile",
    profileButtonAria: "Choose the demo patient profile",
    traceButtonTitle: "Memory and decision trace",
    traceButtonAria: "Open memory and decision trace, {count} events",
    sessionControls: "Session controls",
    close: "Close",
    cancel: "Cancel",
    startingSession: "Starting simulated session…",
    loadingProfiles: "Loading simulated profiles…",

    traceEyebrow: "Memory & Decision Trace",
    traceHeading: "Verifiable events",
    traceEmpty: "Events will appear as the session advances.",
    traceRecognitionSucceeded: "Speech recognition completed",
    traceRecognitionFailed: "Speech recognition did not complete",
    traceEvidenceCounts: "{stable} consistently heard · {uncertain} need review",
    traceVerifiedMemoryCount: "{count} verified memories checked",
    traceContextMemoryCount: "{count} contextual memories checked",
    traceFinalConfirmation: "{method} · {level}",
    traceMemorySaved: "Saved as patient-confirmed memory",
    traceMemoryUpdated: "Existing patient-confirmed memory updated safely",
    traceNeedsClarification: "More clarification is needed",
    traceReadyForFinalReview: "Ready for private final review",
    traceNeedsChoices: "Several expression choices are needed",

    accessEyebrow: "Protected demo",
    accessHeading: "Enter access code",
    accessLabel: "Demo access code",
    accessSubmit: "Open demo",
    accessRejected: "That access code was not accepted.",

    profileEyebrow: "Demo setup",
    profileHeading: "Choose a demo patient",
    profileLabel: "Patient profile",
    profileNote:
      "The profile supplies simulated preferences and context for this demo. It never authorizes a sentence or personal voice.",
    profileAdvanced: "Advanced demo tools",
    profileAdvancedHelp:
      "For evaluators only. Uploaded files must use the structured MeantByMe demo profile format.",
    profileUpload: "Upload a demo profile file",
    profileSubmit: "Continue with this patient",

    editEyebrow: "Patient-authored edit",
    editHeading: "Edit this expression",
    editLabel: "Expression text",
    editNote:
      "Your edit becomes patient-authored content. The expression returns to private review before anything can be spoken.",
    editSubmit: "Save edit",
    editEmpty: "Enter the expression you mean, or cancel.",

    readyEyebrow: "New expression",
    readyTitle: "Ready when you are",
    readyLead:
      "Speak at your own pace. You will review what was heard before AI offers any completed expression.",
    startMicrophone: "Start speaking",
    demoToolsTitle: "Demo input options",
    demoToolsHelp:
      "These controls are for demonstrations and testing. A patient would normally use Start speaking.",
    useDemoFragment: "Use the demo recording",
    chooseWav: "Upload a recording",
    wavHelp: "The demo currently accepts WAV audio files.",
    demoOnlyMock:
      "Demo fragment is available only in mock mode. Record or upload WAV audio.",
    micUnavailable: "Microphone unavailable: {reason}",

    captureEyebrow: "Speech capture",
    captureTitle: "Listening",
    captureLead:
      "Take your time. Pauses are fine — nothing is proposed until you review what was heard.",
    recording: "Recording",
    captureCaption:
      "Microphone capture remains unconfirmed evidence and stops at {seconds} seconds.",
    stopAndReview: "Stop and review",
    useWavInstead: "Use WAV instead",
    maxRecordingReached: "Maximum {seconds}-second recording reached.",

    heardEyebrow: "Heard content",
    heardTitle: "Did we hear these words correctly?",
    heardLead:
      "Confirming this step keeps only the solid words. A dashed word is shown for context but remains unconfirmed.",
    heardSentenceLabel: "What the system heard",
    heardSentenceAria: "Heard words. Solid words were recognized consistently; dashed words need review.",
    stableFragments: "Consistently heard",
    uncertainFragments: "Needs review",
    uncertaintyInfoLabel: "What do the solid and dashed words mean?",
    uncertaintyInfoTitle: "Only solid words are kept",
    uncertaintyInfoBody:
      "Two recognizers agreed on solid words. Dashed words were heard differently and stay unconfirmed. Continuing does not approve a final sentence or authorize speech.",
    yesContinue: "Keep the solid words",
    noStopAttempt: "No, start over",

    rejectedEyebrow: "Input rejected",
    rejectedTitle: "That attempt will not be used.",
    rejectedLead:
      "No candidate was confirmed and no verified memory was written.",
    startNewSession: "Start a new session",

    categoryEyebrow: "One clarification",
    categoryFallback: "What is this about?",
    categoryLead:
      "One question only. It narrows the topic without guessing your sentence.",

    candidatesEyebrow: "Expression candidates",
    candidatesTitle: "Which one matches your meaning?",
    candidatesLead:
      "AI completion and memory can change the order, but they cannot choose for you.",
    candidateHint: "Tap a sentence, or press 1–{count} on a keyboard.",
    candidateDetails: "How this option was completed",
    candidateLabelsOverview:
      "AI-assisted completion means AI added words around the patient’s fragments. Standard confirmation describes the review path, not AI confidence.",
    patientSpan: "Patient: {span}",
    aiSpan: "AI added: {span}",
    memorySupport: "Verified memory support",

    finalRouteEyebrow: "Final review route",
    finalRouteTitle: "Choose the expression to review.",
    finalRouteLead:
      "A low-uncertainty route still requires your explicit selection and final confirmation.",
    privateFlag: "Private earphone readback",
    finalTitle: "Review the whole expression",
    memoryBadge: "Verified memory influenced ranking",
    neutralReadback: "Neutral private readback",
    personalVoiceBlocked: "The patient’s personal voice is still blocked.",
    readbackInfoLabel: "Why is this read in a neutral voice?",
    readbackInfoTitle: "Private review uses a neutral voice",
    readbackInfoBody:
      "This lets you hear the complete sentence without using the patient’s personal voice. Personal voice stays blocked until every required confirmation is complete.",
    readbackCheck:
      "I completed the private readback and this expression is what I mean.",
    strictCheck:
      "I reviewed this high-impact expression again and confirm it is exactly what I mean.",
    l3Check:
      "Most of this expression was suggested by AI. I reviewed it and explicitly choose it.",
    confirmAndSpeak: "Confirm and speak",
    editCompletion: "Edit the completion",
    gateOutstanding: "Still to confirm: {items}.",
    gateReady: "Ready. Nothing is spoken until you press Confirm and speak.",
    outstandingReadback: "the private readback",
    outstandingStrict: "the extra high-impact review",
    outstandingL3: "the AI-suggested expression",
    listSeparator: ", ",

    gestureHintTitle: "Optional earphone shortcuts",
    gestureInfoLabel: "Show optional earphone shortcuts",
    gestureTapOnce: "Tap once",
    gestureTapTwice: "Tap twice",
    gestureHold: "Hold",
    gestureRepeat: "Repeat the readback",
    gestureBack: "Go back a step",
    gestureStop: "Stop",
    gestureFootnote:
      "Earphone taps are a shortcut for these on-screen controls only. Confirming and speaking always needs the button above.",

    completedEyebrow: "Expression completed",
    completedFallback: "Confirmed expression",
    completedLead:
      "The expression was confirmed, authorized for this one use, spoken, and saved as patient-confirmed memory.",
    authorizedOutput: "Authorized personal-voice output",
    authorizedScope: "Authorization scope was this expression only.",
    receiptHeading: "Verification receipt",
    receiptConfirmation: "How it was confirmed",
    receiptLevel: "How this expression was created",
    receiptScope: "Personal-voice permission",
    receiptAiSpans: "Words completed by AI",
    receiptMemory: "Verified memories used",
    receiptTechnical: "Technical details",
    receiptHash: "Final text fingerprint",
    confirmationLargeButton: "On-screen confirmation button",
    confirmationKeyboard: "Keyboard confirmation",
    confirmationScanning: "Switch-scanning confirmation",
    confirmationDwell: "Dwell confirmation",
    confirmationSecondMethod: "Second confirmation method",
    scopeThisExpression: "Only this expression",
    memoryCount: "{count} verified memories",
    sourceL1: "Patient’s direct expression",
    sourceL2: "AI-assisted completion",
    sourceL3: "AI suggestion · extra confirmation",
    sourceInfoLabel: "What does this expression label mean?",
    candidateLabelsInfoLabel: "Explain the expression source and confirmation level",
    candidateLabelsInfoTitle: "About these labels",
    sourceL1InfoTitle: "Patient’s direct expression",
    sourceL1InfoBody:
      "The patient’s input already contained the main sentence. The whole expression is still reviewed before it can be spoken.",
    sourceL2InfoTitle: "AI-assisted completion",
    sourceL2InfoBody:
      "Some words came directly from the patient and AI filled in the missing part. The patient must review and confirm the complete sentence before anything is spoken.",
    sourceL3InfoTitle: "AI suggestion",
    sourceL3InfoBody:
      "Most of the intended expression was suggested by AI rather than directly supplied by the patient. It requires an additional explicit confirmation and can never be selected automatically.",
    none: "None",
    startAnother: "Start another expression",
    compareProfile: "Run same audio with another profile",
    audioUnavailable: "Audio is not available.",

    stoppedEyebrow: "Session stopped",
    stoppedTitle: "Nothing was authorized to speak.",
    stoppedLead:
      "Stopping does not confirm a candidate or write verified memory.",

    fatalEyebrow: "Demo unavailable",
    fatalTitle: "The session could not start.",

    back: "Back",
    noneOfThese: "None of these",
    switchInput: "Switch input",
    requestHelp: "Request help",
    stop: "Stop",

    riskHigh: "Extra confirmation required",
    riskSensitive: "Review with care",
    riskOrdinary: "Standard confirmation",
    riskInfoLabel: "Why is this confirmation level shown?",
    riskOrdinaryInfoTitle: "Standard confirmation",
    riskOrdinaryInfoBody:
      "No high-impact medical, legal, financial, emergency, or major relationship terms were detected. The complete expression still needs final confirmation.",
    riskSensitiveInfoTitle: "Review with care",
    riskSensitiveInfoBody:
      "The content may be personal or sensitive. Review the complete expression carefully before speaking.",
    riskHighInfoTitle: "Extra confirmation required",
    riskHighInfoBody:
      "The expression may affect medical care, legal or financial decisions, emergencies, or major relationships. The runtime requires an additional explicit confirmation.",
    voiceUsed: "Personal voice used",
    voiceAuthorized: "Voice authorized",
    voiceAwaiting: "Awaiting confirmation",
    voiceBlocked: "Voice blocked",
  },

  zh: {
    htmlLang: "zh-Hans",
    otherLanguageLabel: "EN",
    languageToggleTitle: "切换界面语言",
    languageToggleAria: "将界面语言切换为英文",
    appearanceLabel: "外观",
    appearanceAuto: "自动",
    appearanceLight: "浅色",
    appearanceDark: "深色",
    skipLink: "跳到当前决定",
    brandName: "意由我",
    brandTagline: "让话说完，让我做主",
    simulationNotice: "模拟数据，不构成临床准确性声明。",
    noProfile: "未选择画像",
    noProfileControl: "无患者档案（对照）",
    profileButtonTitle: "选择模拟画像",
    profileButtonAria: "选择演示患者档案",
    traceButtonTitle: "记忆与决策轨迹",
    traceButtonAria: "打开记忆与决策轨迹，共 {count} 条事件",
    sessionControls: "会话控制",
    close: "关闭",
    cancel: "取消",
    startingSession: "正在开始模拟会话…",
    loadingProfiles: "正在载入模拟画像…",

    traceEyebrow: "记忆与决策轨迹",
    traceHeading: "可核验事件",
    traceEmpty: "会话推进时，事件会出现在这里。",
    traceRecognitionSucceeded: "语音识别已完成",
    traceRecognitionFailed: "语音识别未完成",
    traceEvidenceCounts: "{stable} 个词识别一致 · {uncertain} 个词仍需复核",
    traceVerifiedMemoryCount: "已检查 {count} 条患者确认记忆",
    traceContextMemoryCount: "已检查 {count} 条情境记忆",
    traceFinalConfirmation: "{method} · {level}",
    traceMemorySaved: "已保存为患者确认记忆",
    traceMemoryUpdated: "已安全更新现有患者确认记忆",
    traceNeedsClarification: "还需要进一步澄清",
    traceReadyForFinalReview: "可以进入私密最终复核",
    traceNeedsChoices: "需要由患者从多个表达中选择",

    accessEyebrow: "受保护的演示",
    accessHeading: "请输入访问码",
    accessLabel: "演示访问码",
    accessSubmit: "进入演示",
    accessRejected: "访问码未被接受。",

    profileEyebrow: "演示设置",
    profileHeading: "选择一位演示患者",
    profileLabel: "患者档案",
    profileNote:
      "档案只为本次演示提供模拟偏好和情境，不能替患者确认句子，也不能授权本人声音。",
    profileAdvanced: "高级演示工具",
    profileAdvancedHelp: "仅供评测人员使用。上传文件必须符合 MeantByMe 的结构化演示档案格式。",
    profileUpload: "上传演示档案文件",
    profileSubmit: "使用这位患者继续",

    editEyebrow: "由患者改写",
    editHeading: "修改这句表达",
    editLabel: "表达内容",
    editNote:
      "你的修改会成为患者本人撰写的内容。修改后会重新进入私密复核，之后才可能被说出。",
    editSubmit: "保存修改",
    editEmpty: "请输入你想表达的句子，或选择取消。",

    readyEyebrow: "新的表达",
    readyTitle: "准备好时，就可以开始",
    readyLead: "按自己的节奏说。AI 提出任何完整表达前，你会先复核系统听到的内容。",
    startMicrophone: "开始说话",
    demoToolsTitle: "演示输入选项",
    demoToolsHelp: "这些控件仅供演示和测试。真实患者通常只需要使用“开始说话”。",
    useDemoFragment: "使用演示录音",
    chooseWav: "上传录音",
    wavHelp: "当前演示支持 WAV 音频文件。",
    demoOnlyMock: "演示片段仅在 mock 模式下可用。请录音或上传 WAV 音频。",
    micUnavailable: "麦克风不可用：{reason}",

    captureEyebrow: "语音采集",
    captureTitle: "正在收听",
    captureLead: "慢慢说，停顿没有关系——在你复核听到的内容之前，不会提出任何表达。",
    recording: "正在录音",
    captureCaption: "麦克风采集仅作为未确认证据，将在 {seconds} 秒时停止。",
    stopAndReview: "停止并复核",
    useWavInstead: "改用 WAV 文件",
    maxRecordingReached: "已达到 {seconds} 秒的录音上限。",

    heardEyebrow: "听到的内容",
    heardTitle: "这些词听对了吗？",
    heardLead: "确认这一步只会保留实线词。虚线词仅用于帮助理解，仍然保持未确认。",
    heardSentenceLabel: "系统听到的内容",
    heardSentenceAria: "系统听到的词。实线词识别一致，虚线词仍需复核。",
    stableFragments: "识别一致",
    uncertainFragments: "仍需复核",
    uncertaintyInfoLabel: "实线词和虚线词分别表示什么？",
    uncertaintyInfoTitle: "只会保留实线词",
    uncertaintyInfoBody:
      "两路识别都听到的词使用实线。听法不一致的词使用虚线，并保持未确认。继续不会确认最终句子，也不会授权说出。",
    yesContinue: "保留听清的词",
    noStopAttempt: "不对，重新输入",

    rejectedEyebrow: "输入已否决",
    rejectedTitle: "这次尝试不会被使用。",
    rejectedLead: "没有确认任何候选，也没有写入已验证记忆。",
    startNewSession: "开始新会话",

    categoryEyebrow: "一个澄清问题",
    categoryFallback: "这是关于什么的？",
    categoryLead: "只问一个问题。它只缩小话题范围，不猜测你的句子。",

    candidatesEyebrow: "表达候选",
    candidatesTitle: "哪一句符合你的意思？",
    candidatesLead: "AI 补全和记忆可以改变排序，但不能替你选择。",
    candidateHint: "点击一句，或用键盘按 1–{count}。",
    candidateDetails: "这句话如何补全",
    candidateLabelsOverview:
      "“AI 辅助补全”表示 AI 围绕患者片段补充了词语；“标准确认”描述的是复核路径，不是 AI 的置信度。",
    patientSpan: "患者原话：{span}",
    aiSpan: "AI 补全：{span}",
    memorySupport: "有已验证记忆支持",

    finalRouteEyebrow: "最终复核路径",
    finalRouteTitle: "请选择要复核的表达。",
    finalRouteLead: "即使不确定度较低，仍然需要你明确选择并做最终确认。",
    privateFlag: "耳机私密播报",
    finalTitle: "复核完整表达",
    memoryBadge: "已验证记忆影响了排序",
    neutralReadback: "中性私密回读",
    personalVoiceBlocked: "患者本人的声音仍处于封锁状态。",
    readbackInfoLabel: "为什么使用中性声音回读？",
    readbackInfoTitle: "私密复核使用中性声音",
    readbackInfoBody:
      "这样可以先听完整句子，而不提前使用患者本人的声音。所有必要确认完成前，本人声音会一直保持封锁。",
    readbackCheck: "我已完成私密回读，这句话就是我的意思。",
    strictCheck: "我已再次复核这句影响较大的表达，并确认它准确表达了我的意思。",
    l3Check: "这句话大部分由 AI 建议。我已经完整复核，并明确选择这句话。",
    confirmAndSpeak: "确认并说出",
    editCompletion: "修改补全内容",
    gateOutstanding: "还需确认：{items}。",
    gateReady: "已就绪。在你按下“确认并说出”之前，不会说出任何内容。",
    outstandingReadback: "私密回读",
    outstandingStrict: "额外的重要内容复核",
    outstandingL3: "AI 建议表达",
    listSeparator: "、",

    gestureHintTitle: "可选的耳机快捷操作",
    gestureInfoLabel: "查看可选的耳机快捷操作",
    gestureTapOnce: "轻敲一次",
    gestureTapTwice: "轻敲两次",
    gestureHold: "长按",
    gestureRepeat: "重听一次回读",
    gestureBack: "返回上一步",
    gestureStop: "停止",
    gestureFootnote:
      "耳机敲击只是上面这些屏幕操作的快捷方式。确认并说出，始终需要按上方按钮。",

    completedEyebrow: "表达已完成",
    completedFallback: "已确认的表达",
    completedLead: "这句话已经确认，仅获得本次说出授权，并保存为患者确认的记忆。",
    authorizedOutput: "已授权的本人声音输出",
    authorizedScope: "授权范围仅限这一句表达。",
    receiptHeading: "可核验回执",
    receiptConfirmation: "如何完成确认",
    receiptLevel: "这句话如何形成",
    receiptScope: "本人声音权限",
    receiptAiSpans: "由 AI 补全的词",
    receiptMemory: "使用的已验证记忆",
    receiptTechnical: "技术详情",
    receiptHash: "最终文本指纹",
    confirmationLargeButton: "屏幕确认按钮",
    confirmationKeyboard: "键盘确认",
    confirmationScanning: "开关扫描确认",
    confirmationDwell: "停留确认",
    confirmationSecondMethod: "第二种确认方式",
    scopeThisExpression: "仅限这句话",
    memoryCount: "{count} 条已验证记忆",
    sourceL1: "患者直接表达",
    sourceL2: "AI 辅助补全",
    sourceL3: "AI 主动建议 · 需额外确认",
    sourceInfoLabel: "这个表达来源标签是什么意思？",
    candidateLabelsInfoLabel: "解释表达来源和确认级别",
    candidateLabelsInfoTitle: "这些标签是什么意思",
    sourceL1InfoTitle: "患者直接表达",
    sourceL1InfoBody: "患者输入已经包含主要句意。即使如此，完整表达在说出前仍需最终复核。",
    sourceL2InfoTitle: "AI 辅助补全",
    sourceL2InfoBody:
      "句子一部分来自患者原话，缺失部分由 AI 补全。在说出任何内容前，患者必须完整复核并确认整句话。",
    sourceL3InfoTitle: "AI 主动建议",
    sourceL3InfoBody:
      "这句话的大部分意思由 AI 主动建议，而不是患者直接提供。因此必须增加一次明确确认，也绝不能被自动选择。",
    none: "无",
    startAnother: "开始新的表达",
    compareProfile: "用同一段音频换一个画像",
    audioUnavailable: "音频不可用。",

    stoppedEyebrow: "会话已停止",
    stoppedTitle: "没有任何内容获得说出授权。",
    stoppedLead: "停止不会确认候选，也不会写入已验证记忆。",

    fatalEyebrow: "演示不可用",
    fatalTitle: "会话无法启动。",

    back: "返回",
    noneOfThese: "都不是",
    switchInput: "切换输入方式",
    requestHelp: "请求帮助",
    stop: "停止",

    riskHigh: "需要额外确认",
    riskSensitive: "请谨慎复核",
    riskOrdinary: "标准确认",
    riskInfoLabel: "为什么显示这个确认级别？",
    riskOrdinaryInfoTitle: "标准确认",
    riskOrdinaryInfoBody:
      "系统未检测到医疗、法律、财务、紧急事件或重大关系等影响较大的内容。整句话仍然需要最终确认。",
    riskSensitiveInfoTitle: "请谨慎复核",
    riskSensitiveInfoBody: "内容可能涉及个人或敏感事项。请在说出前仔细复核完整表达。",
    riskHighInfoTitle: "需要额外确认",
    riskHighInfoBody:
      "这句话可能影响医疗、法律或财务决定、紧急事件或重大关系。运行时会强制要求额外的明确确认。",
    voiceUsed: "已使用本人声音",
    voiceAuthorized: "声音已授权",
    voiceAwaiting: "等待确认",
    voiceBlocked: "声音已封锁",
  },
};

const stageLabelKeys = {
  ready: "stageReady",
  capturing: "stageCapturing",
  heard_content_review: "stageHeard",
  category_clarification: "stageCategory",
  candidate_selection: "stageCandidates",
  final_review: "stageFinalReview",
  patient_confirmed: "stageConfirmed",
  voice_authorized: "stageVoiceAuthorized",
  spoken: "stageSpoken",
  memory_updated: "stageMemoryUpdated",
  completed: "stageCompleted",
  stopped: "stageStopped",
};

Object.assign(strings.en, {
  stageReady: "Ready",
  stageCapturing: "Listening",
  stageHeard: "Check what was heard",
  stageCategory: "Clarify the topic",
  stageCandidates: "Choose an expression",
  stageFinalReview: "Private final review",
  stageConfirmed: "Confirmed",
  stageVoiceAuthorized: "Voice authorized",
  stageSpoken: "Spoken",
  stageMemoryUpdated: "Memory updated",
  stageCompleted: "Completed",
  stageStopped: "Stopped",
  stageProcessing: "Processing",
});

Object.assign(strings.zh, {
  stageReady: "就绪",
  stageCapturing: "正在收听",
  stageHeard: "复核听到的内容",
  stageCategory: "澄清话题",
  stageCandidates: "选择表达",
  stageFinalReview: "私密最终复核",
  stageConfirmed: "已确认",
  stageVoiceAuthorized: "声音已授权",
  stageSpoken: "已说出",
  stageMemoryUpdated: "记忆已更新",
  stageCompleted: "已完成",
  stageStopped: "已停止",
  stageProcessing: "正在处理",
});

const eventLabels = {
  en: {
    SESSION_STARTED: "Session started",
    AUDIO_CAPTURED: "Speech captured",
    ASR_RESULT_RECEIVED: "Speech recognition result received",
    EVIDENCE_EXTRACTED: "Clear and uncertain words identified",
    MEMORY_RETRIEVED: "Verified expression memory retrieved",
    CONTEXT_RETRIEVED: "Situational memory retrieved",
    UNCERTAINTY_ASSESSED: "Next review step determined",
    CLARIFICATION_REQUESTED: "Clarification requested",
    CANDIDATES_GENERATED: "Expression candidates generated",
    CANDIDATES_RERANKED: "Candidates ordered by evidence",
    PATIENT_SELECTION_RECEIVED: "Patient selection received",
    PRIVATE_READBACK_READY: "Private readback ready",
    FINAL_CONFIRMATION_RECEIVED: "Explicit confirmation received",
    VOICE_AUTHORIZATION_GRANTED: "Personal voice authorization granted",
    VOICE_AUTHORIZATION_BLOCKED: "Personal voice authorization blocked",
    TTS_FAILED: "Speech synthesis failed",
    EXPRESSION_SPOKEN: "Confirmed expression spoken",
    EXPRESSION_RECEIPT_CREATED: "Verification receipt created",
    VERIFIED_MEMORY_WRITTEN: "Verified memory updated",
    SESSION_COMPLETED: "Session completed",
    SESSION_STOPPED: "Session stopped",
    COMMAND_REJECTED: "Command rejected",
    INPUT_METHOD_SWITCH_REQUESTED: "Input method switch requested",
    HELP_REQUESTED: "Help requested",
  },
  zh: {
    SESSION_STARTED: "会话已开始",
    AUDIO_CAPTURED: "已采集语音",
    ASR_RESULT_RECEIVED: "已收到语音识别结果",
    EVIDENCE_EXTRACTED: "已识别听清与待复核的词",
    MEMORY_RETRIEVED: "已检索已验证表达记忆",
    CONTEXT_RETRIEVED: "已检索情境记忆",
    UNCERTAINTY_ASSESSED: "已决定下一步复核方式",
    CLARIFICATION_REQUESTED: "已请求澄清",
    CANDIDATES_GENERATED: "已生成表达候选",
    CANDIDATES_RERANKED: "已按证据排序候选",
    PATIENT_SELECTION_RECEIVED: "已收到患者选择",
    PRIVATE_READBACK_READY: "私密回读已就绪",
    FINAL_CONFIRMATION_RECEIVED: "已收到明确确认",
    VOICE_AUTHORIZATION_GRANTED: "已授予本人声音授权",
    VOICE_AUTHORIZATION_BLOCKED: "本人声音授权被拒",
    TTS_FAILED: "语音合成失败",
    EXPRESSION_SPOKEN: "已说出确认的表达",
    EXPRESSION_RECEIPT_CREATED: "已生成可核验回执",
    VERIFIED_MEMORY_WRITTEN: "已更新已验证记忆",
    SESSION_COMPLETED: "会话已完成",
    SESSION_STOPPED: "会话已停止",
    COMMAND_REJECTED: "指令被拒绝",
    INPUT_METHOD_SWITCH_REQUESTED: "已请求切换输入方式",
    HELP_REQUESTED: "已请求帮助",
  },
};

const icons = {
  headphone: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M3 18v-6a9 9 0 0 1 18 0v6" />
    <path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3z" />
    <path d="M3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z" />
  </svg>`,
  check: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <polyline points="20 6 9 17 4 12" />
  </svg>`,
  halt: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M5 5 19 19" />
    <path d="M19 5 5 19" />
  </svg>`,
};

const appState = {
  demoToken: sessionStorage.getItem("meantbyme_demo_token") || "",
  sessionId: "",
  sessionToken: "",
  model: null,
  recorder: null,
  recordingStartedAt: 0,
  recordingTimer: null,
  recordingAutoStopStarted: false,
  maxAudioSeconds: 20,
  audioUrls: [],
  readbackCompleted: false,
  profiles: [],
  profileRef: "no_profile",
  profileLanguage: "en",
  replayAfterCreate: false,
  lastAudioBlob: null,
  // UI-only bookkeeping.
  uiLanguage: "en",
  appearance: "auto",
  languagePinned: false,
  stageKey: "",
  requestInFlight: false,
  hasInteracted: false,
  waveformFrame: null,
  traceRendered: 0,
};

const stageProgress = {
  ready: 6,
  capturing: 14,
  heard_content_review: 34,
  category_clarification: 48,
  candidate_selection: 62,
  final_review: 78,
  patient_confirmed: 86,
  voice_authorized: 90,
  spoken: 94,
  memory_updated: 97,
  completed: 100,
  stopped: 100,
};

/* ── i18n ─────────────────────────────────────────────────────────────────── */

function t(key, vars) {
  const table = strings[appState.uiLanguage] || strings.en;
  let value = table[key] ?? strings.en[key] ?? key;
  if (vars) {
    Object.entries(vars).forEach(([name, replacement]) => {
      value = value.split(`{${name}}`).join(String(replacement));
    });
  }
  return value;
}

function initialLanguage() {
  const stored = sessionStorage.getItem(LANGUAGE_KEY);
  if (stored && strings[stored]) {
    appState.languagePinned = true;
    return stored;
  }
  return (navigator.language || "en").toLowerCase().startsWith("zh") ? "zh" : "en";
}

function suggestedInterfaceLanguage(option) {
  const label = option?.textContent || "";
  if (/[\u3400-\u9fff]/.test(label)) return "zh";
  return (option?.dataset.language || "en").toLowerCase().startsWith("zh")
    ? "zh"
    : "en";
}

function initialAppearance() {
  const stored = sessionStorage.getItem(APPEARANCE_KEY);
  return ["auto", "light", "dark"].includes(stored) ? stored : "auto";
}

function appearanceIsDark() {
  return appState.appearance === "dark"
    || (appState.appearance === "auto" && systemDarkAppearance.matches);
}

function updateBrandAssets() {
  const darkSuffix = appearanceIsDark() ? "-dark" : "";
  if (ui.brandMark) {
    ui.brandMark.src = `/assets/brand/logo-mark${darkSuffix}.svg`;
  }
  if (ui.launchLockup) {
    const language = appState.uiLanguage === "zh" ? "zh" : "en";
    ui.launchLockup.src = `/assets/brand/logo-lockup-${language}${darkSuffix}.png`;
  }
}

function applyAppearance() {
  document.documentElement.dataset.theme = appState.appearance;
  if (ui.appearanceSelect) ui.appearanceSelect.value = appState.appearance;
  const dark = appearanceIsDark();
  if (ui.themeColorMeta) {
    ui.themeColorMeta.content = dark ? "#000000" : "#f2f2f7";
  }
  if (ui.statusBarMeta) {
    ui.statusBarMeta.content = dark ? "black-translucent" : "default";
  }
  updateBrandAssets();
}

function setAppearance(appearance) {
  if (!["auto", "light", "dark"].includes(appearance)) return;
  appState.appearance = appearance;
  sessionStorage.setItem(APPEARANCE_KEY, appearance);
  applyAppearance();
}

/** Applies the string table to markup that is not re-rendered per stage. */
function applyStaticStrings() {
  document.documentElement.lang = t("htmlLang");
  updateBrandAssets();
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-title]").forEach((node) => {
    node.title = t(node.dataset.i18nTitle);
  });
  document.querySelectorAll("[data-i18n-label]").forEach((node) => {
    node.setAttribute("aria-label", t(node.dataset.i18nLabel));
  });
  document.querySelectorAll("[data-i18n-aria-label]").forEach((node) => {
    node.setAttribute("aria-label", t(node.dataset.i18nAriaLabel));
  });
  ui.languageToggle.textContent = t("otherLanguageLabel");
  ui.languageToggle.setAttribute("aria-label", t("languageToggleAria"));
  updateTraceButtonLabel();
}

function setLanguage(language, { pin = false } = {}) {
  if (!strings[language] || language === appState.uiLanguage) return;
  appState.uiLanguage = language;
  if (pin) {
    appState.languagePinned = true;
    sessionStorage.setItem(LANGUAGE_KEY, language);
  }
  applyStaticStrings();
  if (appState.model) {
    // Re-render everything that carries translated copy.
    const stage = appState.stageKey;
    appState.stageKey = "";
    update(appState.model);
    appState.stageKey = stage;
  }
}

/**
 * The web demo mirrors a native launch screen plus a short in-app brand
 * transition. It never gates the runtime: initialization happens underneath,
 * and the layer removes itself after its own exit animation.
 */
function setupLaunchScreen() {
  if (!ui.launchScreen) return;
  let removed = false;
  const remove = () => {
    if (removed) return;
    removed = true;
    ui.launchScreen.remove();
  };
  ui.launchScreen.addEventListener("animationend", (event) => {
    if (event.target === ui.launchScreen && event.animationName === "launch-screen-out") {
      remove();
    }
  });
  window.setTimeout(remove, reducedMotion.matches ? 500 : 1800);
}

/* ── API ──────────────────────────────────────────────────────────────────── */

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (appState.demoToken) headers.set("X-Demo-Token", appState.demoToken);
  if (appState.sessionToken) headers.set("X-Demo-Session", appState.sessionToken);
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch (_) {
      // Keep the status-only message.
    }
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  return response;
}

async function initialize() {
  appState.appearance = initialAppearance();
  appState.uiLanguage = initialLanguage();
  applyAppearance();
  applyStaticStrings();
  if (dockedTrace.matches) openTrace();
  try {
    const health = await (await fetch("/api/health")).json();
    ui.mode.textContent = health.mode.toUpperCase();
    appState.maxAudioSeconds = Number(health.max_audio_seconds) || 20;
    if (health.demo_access_configured && !appState.demoToken) {
      ui.accessDialog.showModal();
      ui.accessCode.focus();
      return;
    }
    await openProfileSetup();
  } catch (error) {
    showFatal(error.message);
  }
}

async function createSession() {
  clearAudioUrls();
  appState.sessionId = "";
  appState.sessionToken = "";
  appState.model = null;
  appState.readbackCompleted = false;
  appState.traceRendered = 0;
  showLoading(t("startingSession"));
  try {
    const response = await api("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        language: appState.profileLanguage,
        profile_ref: appState.profileRef,
      }),
    });
    const payload = await response.json();
    appState.sessionId = payload.session.session_id;
    appState.sessionToken = payload.session_token;
    delete payload.session_token;
    update(payload);
    if (appState.replayAfterCreate && appState.lastAudioBlob) {
      appState.replayAfterCreate = false;
      await uploadAudio(appState.lastAudioBlob);
      await sendCommand("start_capture");
      if (appState.model.session.stage === "capturing") {
        await sendCommand("stop_capture");
      }
    }
  } catch (error) {
    if (error.status === 401) {
      rejectAccess();
      return;
    }
    showFatal(error.message);
  }
}

function rejectAccess() {
  appState.demoToken = "";
  sessionStorage.removeItem("meantbyme_demo_token");
  ui.accessError.textContent = t("accessRejected");
  ui.accessDialog.showModal();
  ui.accessCode.focus();
}

async function openProfileSetup({ replay = false } = {}) {
  showLoading(t("loadingProfiles"));
  try {
    const response = await api("/api/profiles");
    const payload = await response.json();
    appState.profiles = payload.profiles;
    appState.replayAfterCreate = replay;
    renderProfileOptions();
    ui.profileError.textContent = "";
    ui.profileDialog.showModal();
  } catch (error) {
    if (error.status === 401) {
      rejectAccess();
      return;
    }
    showFatal(error.message);
  }
}

function displayProfileLabel(profile) {
  if (!profile) return t("noProfile");
  if (
    profile.profile_ref === "no_profile"
    || profile.profile_id === "no_profile"
  ) {
    return t("noProfileControl");
  }
  return profile.label;
}

function renderProfileOptions(extraProfile = null) {
  const profiles = extraProfile
    ? [...appState.profiles, extraProfile]
    : appState.profiles;
  ui.profileSelect.innerHTML = "";
  profiles.forEach((profile) => {
    const option = document.createElement("option");
    option.value = profile.profile_ref;
    option.textContent = displayProfileLabel(profile);
    option.dataset.language = profile.default_language;
    if (profile.profile_ref === appState.profileRef) option.selected = true;
    ui.profileSelect.append(option);
  });
}

async function sendCommand(command, payload = {}, confirmationMethod = null) {
  // Stop stays reachable while another command is in flight; anything else
  // queued behind a pending request is dropped rather than raced.
  if (appState.requestInFlight && command !== "stop") return;
  appState.hasInteracted = true;
  setStatus("");
  appState.requestInFlight = true;
  setInteractionDisabled(true);
  try {
    const response = await api(`/api/sessions/${appState.sessionId}/commands`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        command,
        payload,
        confirmation_method: confirmationMethod,
      }),
    });
    update(await response.json());
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    appState.requestInFlight = false;
    setInteractionDisabled(false);
  }
}

async function uploadAudio(blob) {
  appState.lastAudioBlob = blob;
  const response = await api(`/api/sessions/${appState.sessionId}/audio`, {
    method: "POST",
    headers: { "Content-Type": "audio/wav" },
    body: blob,
  });
  return response.json();
}

function update(payload) {
  appState.model = payload;
  const stage = payload.session.stage;
  const percent = stageProgress[stage] || 10;
  ui.mode.textContent = payload.mode.toUpperCase();
  ui.progressLabel.textContent = stageLabel(stage);
  ui.progress.style.width = `${percent}%`;
  ui.progressTrack.setAttribute("aria-valuenow", String(percent));
  ui.progressTrack.dataset.complete = String(percent >= 100);
  ui.voice.textContent = voiceLabel(payload.session.personal_voice_status);
  ui.voice.dataset.status = payload.session.personal_voice_status;
  ui.profileButton.querySelector("span").textContent =
    displayProfileLabel(payload.profile);
  renderDecision();
  renderControls();
  renderTrace();
}

function updateTraceButtonLabel() {
  ui.traceButton.setAttribute(
    "aria-label",
    t("traceButtonAria", { count: ui.traceCount.textContent || "0" }),
  );
}

function stageLabel(stage) {
  const key = stageLabelKeys[stage];
  return key ? t(key) : stage;
}

/* ── Stage rendering ──────────────────────────────────────────────────────── */

/**
 * Replaces the stage body and repopulates the action bar.
 *
 * `primary` describes the actions that belong in the thumb zone rather than in
 * the scrolling body — on a phone the stage can be far taller than the viewport,
 * so the decisive button must not live inside the scroll.
 */
function renderStage({ key, body, primary = [] }) {
  const changed = key !== appState.stageKey;
  appState.stageKey = key;
  stopWaveform();
  setGate("");
  ui.decision.innerHTML = `<div class="stage">${body}</div>`;
  ui.primaryActions.innerHTML = "";
  primary.forEach((action) => {
    const button = makeButton(action.label, action.className || "button button-primary");
    if (action.id) button.id = action.id;
    if (action.disabled) button.disabled = true;
    button.addEventListener("click", action.onClick);
    ui.primaryActions.append(button);
  });
  if (changed) orientStage(key);
}

/**
 * Orient the patient after the complete stage DOM has been populated.
 *
 * Candidate cards are appended immediately after ``renderStage`` returns.
 * Focusing synchronously used to let scroll anchoring move the workspace so
 * the question and top of candidate 1 were hidden. The animation-frame boundary
 * waits for those children, then resets scroll before and after focus.
 */
function orientStage(key) {
  requestAnimationFrame(() => {
    if (appState.stageKey !== key) return;
    ui.workspace.scrollTop = 0;
    const title = ui.decision.querySelector(".stage-title");
    if (title && appState.hasInteracted) {
      title.tabIndex = -1;
      title.focus({ preventScroll: true });
    }
    ui.workspace.scrollTop = 0;
  });
}

function renderDecision() {
  clearAudioUrls();
  const model = appState.model;
  const stage = model.session.stage;
  if (model.failure_status === "heard_content_rejected") {
    renderRejectedHeardContent();
    return;
  }
  if (stage === "ready") renderReady();
  else if (stage === "capturing") renderCapturing();
  else if (stage === "heard_content_review") renderHeardReview();
  else if (stage === "category_clarification") renderCategory();
  else if (stage === "candidate_selection") renderCandidates();
  else if (stage === "final_review") renderFinalReview();
  else if (stage === "completed") renderCompleted();
  else if (stage === "stopped") renderStopped();
  else renderProcessing(stage);
}

function renderReady() {
  renderStage({
    key: "ready",
    body: `
      <span class="eyebrow">${escapeHtml(t("readyEyebrow"))}</span>
      <h1 id="stage-title" class="stage-title">${escapeHtml(t("readyTitle"))}</h1>
      <p class="lead">${escapeHtml(t("readyLead"))}</p>
      <details class="demo-tools">
        <summary>${escapeHtml(t("demoToolsTitle"))}</summary>
        <p class="capture-caption">${escapeHtml(t("demoToolsHelp"))}</p>
        <div class="action-grid">
          <button id="use-demo" class="button button-secondary" type="button">${escapeHtml(t("useDemoFragment"))}</button>
          <label class="button button-secondary" for="wav-input">${escapeHtml(t("chooseWav"))}</label>
          <input id="wav-input" class="visually-hidden" type="file" accept=".wav,audio/wav">
        </div>
        <p class="capture-caption">${escapeHtml(t("wavHelp"))}</p>
      </details>
    `,
    primary: [{ id: "start-microphone", label: t("startMicrophone"), onClick: startMicrophone }],
  });
  document.querySelector("#use-demo").addEventListener("click", useDemoFragment);
  document.querySelector("#wav-input").addEventListener("change", useWavFile);
}

async function startMicrophone() {
  setStatus("");
  appState.hasInteracted = true;
  try {
    appState.recorder = await BrowserWavRecorder.create();
    await sendCommand("start_capture");
    if (appState.model.session.stage !== "capturing") return;
    appState.recorder.start();
    appState.recordingStartedAt = Date.now();
    startRecordingTimer();
    startWaveform();
  } catch (error) {
    appState.recorder = null;
    setStatus(t("micUnavailable", { reason: error.message }), "error");
  }
}

async function useDemoFragment() {
  if (appState.model.mode !== "mock") {
    setStatus(t("demoOnlyMock"), "info");
    return;
  }
  await sendCommand("start_capture");
  if (appState.model.session.stage === "capturing") {
    await sendCommand("stop_capture");
  }
}

async function useWavFile(event) {
  const [file] = event.target.files;
  if (!file) return;
  appState.hasInteracted = true;
  try {
    await uploadAudio(file);
    await sendCommand("start_capture");
    if (appState.model.session.stage !== "capturing") return;
    await sendCommand("stop_capture");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

function renderCapturing() {
  const bars = Array.from(
    { length: WAVEFORM_BARS },
    (_, index) => `<span style="--i:${index}"></span>`,
  ).join("");
  renderStage({
    key: "capturing",
    body: `
      <span class="eyebrow">${escapeHtml(t("captureEyebrow"))}</span>
      <h1 id="stage-title" class="stage-title">${escapeHtml(t("captureTitle"))}</h1>
      <p class="lead">${escapeHtml(t("captureLead"))}</p>
      <div class="capture-panel">
        <p class="capture-status">
          <span class="record-dot" aria-hidden="true"></span>
          ${escapeHtml(t("recording"))}
        </p>
        <div id="waveform" class="waveform" data-source="idle" aria-hidden="true">${bars}</div>
        <div class="capture-meta">
          <span id="capture-time" class="capture-time">00:00</span>
          <span class="capture-caption">${escapeHtml(t("captureCaption", { seconds: appState.maxAudioSeconds }))}</span>
        </div>
      </div>
      <div class="action-grid">
        <label class="button button-secondary" for="capture-wav-input">${escapeHtml(t("useWavInstead"))}</label>
        <input id="capture-wav-input" class="visually-hidden" type="file" accept=".wav,audio/wav">
      </div>
    `,
    primary: [{ id: "stop-microphone", label: t("stopAndReview"), onClick: stopMicrophone }],
  });
  document.querySelector("#capture-wav-input").addEventListener("change", replaceWithWav);
  updateCaptureClock();
  if (appState.recorder) startWaveform();
}

/**
 * Drives the capture bars from the live microphone level, so the waveform
 * reflects what the device is actually hearing rather than a decorative loop.
 */
function startWaveform() {
  stopWaveform();
  const waveform = document.querySelector("#waveform");
  if (!waveform || !appState.recorder) return;
  if (reducedMotion.matches) {
    waveform.dataset.source = "static";
    return;
  }
  const bars = Array.from(waveform.children);
  const smoothed = new Array(bars.length).fill(0.08);
  const frame = () => {
    if (!waveform.isConnected || !appState.recorder) {
      stopWaveform();
      return;
    }
    // Null while the recorder exists but is not armed yet: keep the idle
    // breathing rather than freezing the bars flat.
    const levels = appState.recorder.readLevels(bars.length);
    if (levels) {
      waveform.dataset.source = "microphone";
      levels.forEach((level, index) => {
        const current = smoothed[index];
        // Rise fast so speech onsets are visible, fall slowly so it reads calm.
        smoothed[index] = current + (level - current) * (level > current ? 0.6 : 0.14);
        bars[index].style.setProperty("--level", Math.max(0.06, smoothed[index]).toFixed(3));
      });
    }
    appState.waveformFrame = window.requestAnimationFrame(frame);
  };
  appState.waveformFrame = window.requestAnimationFrame(frame);
}

function stopWaveform() {
  if (appState.waveformFrame) window.cancelAnimationFrame(appState.waveformFrame);
  appState.waveformFrame = null;
}

async function stopMicrophone() {
  stopRecordingTimer();
  stopWaveform();
  try {
    if (appState.recorder) {
      const wav = await appState.recorder.stop();
      appState.recorder = null;
      await uploadAudio(wav);
    }
    await sendCommand("stop_capture");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

async function replaceWithWav(event) {
  const [file] = event.target.files;
  if (!file) return;
  stopRecordingTimer();
  stopWaveform();
  if (appState.recorder) {
    await appState.recorder.cancel();
    appState.recorder = null;
  }
  try {
    await uploadAudio(file);
    await sendCommand("stop_capture");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

function renderHeardReview() {
  renderStage({
    key: "heard_content_review",
    body: `
      <span class="eyebrow">${escapeHtml(t("heardEyebrow"))}</span>
      <h1 id="stage-title" class="stage-title">${escapeHtml(t("heardTitle"))}</h1>
      <p class="lead">${escapeHtml(t("heardLead"))}</p>
      <div class="evidence-band">
        <div class="evidence-heading">
          <span class="evidence-label">${escapeHtml(t("heardSentenceLabel"))}</span>
          ${infoDisclosureMarkup(
            t("uncertaintyInfoLabel"),
            t("uncertaintyInfoTitle"),
            t("uncertaintyInfoBody"),
          )}
        </div>
        ${heardSequenceMarkup()}
        <div class="evidence-legend" aria-hidden="true">
          <span><i class="legend-swatch stable"></i>${escapeHtml(t("stableFragments"))}</span>
          <span><i class="legend-swatch uncertain"></i>${escapeHtml(t("uncertainFragments"))}</span>
        </div>
      </div>
      <div class="action-grid">
        <button id="heard-no" class="button button-secondary" type="button">${escapeHtml(t("noStopAttempt"))}</button>
      </div>
    `,
    primary: [{
      id: "heard-yes",
      label: t("yesContinue"),
      onClick: () => sendCommand("confirm_heard_content"),
    }],
  });
  document.querySelector("#heard-no").addEventListener("click", () => sendCommand("reject_heard_content"));
}

function renderRejectedHeardContent() {
  renderStage({
    key: "heard_content_rejected",
    body: `
      <div class="result-headline">
        <div class="result-mark halted" aria-hidden="true">${icons.halt}</div>
        <span class="eyebrow">${escapeHtml(t("rejectedEyebrow"))}</span>
        <h1 id="stage-title" class="stage-title">${escapeHtml(t("rejectedTitle"))}</h1>
        <p class="lead">${escapeHtml(t("rejectedLead"))}</p>
      </div>
    `,
    primary: [{ label: t("startNewSession"), onClick: () => createSession() }],
  });
}

function renderCategory() {
  const options = appState.model.session.clarification_options;
  renderStage({
    key: "category_clarification",
    body: `
      <span class="eyebrow">${escapeHtml(t("categoryEyebrow"))}</span>
      <h1 id="stage-title" class="stage-title">${escapeHtml(appState.model.session.clarification_question || t("categoryFallback"))}</h1>
      <p class="lead">${escapeHtml(t("categoryLead"))}</p>
      <div id="category-options" class="action-grid"></div>
    `,
  });
  const target = document.querySelector("#category-options");
  options.forEach((option) => {
    const button = makeButton(option, "button button-secondary");
    button.addEventListener("click", () => sendCommand("select_category", { category: option }));
    target.append(button);
  });
}

function renderCandidates() {
  renderStage({
    key: "candidate_selection",
    body: `
      <span class="eyebrow">${escapeHtml(t("candidatesEyebrow"))}</span>
      <h1 id="stage-title" class="stage-title">${escapeHtml(t("candidatesTitle"))}</h1>
      <p class="lead">${escapeHtml(t("candidatesLead"))}</p>
      <div class="candidate-label-help">
        ${infoDisclosureMarkup(
          t("candidateLabelsInfoLabel"),
          t("candidateLabelsInfoTitle"),
          t("candidateLabelsOverview"),
        )}
      </div>
      <ul id="candidate-list" class="candidate-list"></ul>
      <p class="candidate-hint">${escapeHtml(t("candidateHint", { count: appState.model.session.candidates.length }))}</p>
    `,
  });
  renderCandidateList(document.querySelector("#candidate-list"));
}

function renderCandidateList(target) {
  appState.model.session.candidates.forEach((candidate, index) => {
    const node = ui.candidateTemplate.content.cloneNode(true);
    const item = node.querySelector(".candidate-item");
    item.style.setProperty("--i", String(index));
    node.querySelector(".candidate-index").textContent = index + 1;
    node.querySelector(".candidate-text").textContent = candidate.text;
    node.querySelector(".candidate-meta").textContent =
      `${sourceLevelLabel(candidate.source_level)} · ${riskLabel(candidate.risk_level)}`;
    const select = node.querySelector(".candidate-select");
    select.dataset.candidateIndex = String(index);
    select.addEventListener("click", () => selectCandidate(candidate.id));
    target.append(node);
  });
}

function selectCandidate(candidateId) {
  appState.readbackCompleted = false;
  sendCommand("select_candidate", { candidate_id: candidateId });
}

function renderFinalReview() {
  const selected = appState.model.selected_candidate;
  if (!selected) {
    renderStage({
      key: "final_review_select",
      body: `
        <span class="eyebrow">${escapeHtml(t("finalRouteEyebrow"))}</span>
        <h1 id="stage-title" class="stage-title">${escapeHtml(t("finalRouteTitle"))}</h1>
        <p class="lead">${escapeHtml(t("finalRouteLead"))}</p>
        <div class="candidate-label-help">
          ${infoDisclosureMarkup(
            t("candidateLabelsInfoLabel"),
            t("candidateLabelsInfoTitle"),
            t("candidateLabelsOverview"),
          )}
        </div>
        <ul id="candidate-list" class="candidate-list"></ul>
        <p class="candidate-hint">${escapeHtml(t("candidateHint", { count: appState.model.session.candidates.length }))}</p>
      `,
    });
    renderCandidateList(document.querySelector("#candidate-list"));
    return;
  }
  const strict = appState.model.strict;
  const l3 = selected.source_level === "L3";
  renderStage({
    key: "final_review",
    body: `
      <p class="private-flag">${icons.headphone} ${escapeHtml(t("privateFlag"))}</p>
      <h1 id="stage-title" class="stage-title">${escapeHtml(t("finalTitle"))}</h1>
      <div class="final-expression">${escapeHtml(selected.text)}</div>
      <div class="review-meta">
        <span class="source-badge">${escapeHtml(sourceLevelLabel(selected.source_level))}</span>
        <span class="risk-badge ${escapeHtml(selected.risk_level)}">${escapeHtml(riskLabel(selected.risk_level))}</span>
        ${selected.memory_support_ids.length ? `<span class="memory-badge">${escapeHtml(t("memoryBadge"))}</span>` : ""}
      </div>
      <details class="candidate-details final-details">
        <summary>${escapeHtml(t("candidateDetails"))}</summary>
        <div class="candidate-provenance" id="review-provenance"></div>
        <div class="final-details-explanation">
          <p><strong>${escapeHtml(sourceLevelLabel(selected.source_level))}:</strong>
            ${escapeHtml(sourceInfoBody(selected.source_level))}</p>
          <p><strong>${escapeHtml(riskLabel(selected.risk_level))}:</strong>
            ${escapeHtml(riskInfoBody(selected.risk_level))}</p>
        </div>
      </details>
      <div class="audio-review">
        <div class="audio-review-head">
          <strong>${escapeHtml(t("neutralReadback"))}</strong>
          ${infoDisclosureMarkup(
            t("readbackInfoLabel"),
            t("readbackInfoTitle"),
            t("readbackInfoBody"),
          )}
        </div>
        <span class="capture-caption">${escapeHtml(t("personalVoiceBlocked"))}</span>
        <audio id="neutral-audio" controls preload="none" aria-label="${escapeHtml(t("neutralReadback"))}"></audio>
      </div>
      <div class="confirmation-list">
        <label class="confirmation-check">
          <input id="readback-check" type="checkbox">
          <span>${escapeHtml(t("readbackCheck"))}</span>
        </label>
        ${strict ? `
          <label class="confirmation-check">
            <input id="strict-check" type="checkbox">
            <span>${escapeHtml(t("strictCheck"))}</span>
          </label>` : ""}
        ${l3 ? `
          <label class="confirmation-check">
            <input id="l3-check" type="checkbox">
            <span>${escapeHtml(t("l3Check"))}</span>
          </label>` : ""}
      </div>
      <div class="action-grid">
        <button id="edit-expression" class="button button-secondary" type="button">${escapeHtml(t("editCompletion"))}</button>
      </div>
      ${gestureHintMarkup()}
    `,
    primary: [{
      id: "final-confirm",
      label: t("confirmAndSpeak"),
      disabled: true,
      onClick: () => sendCommand(
        "final_confirm",
        {
          private_readback_completed: true,
          strict_confirmation: Boolean(strict),
          l3_confirmation: Boolean(l3),
        },
        "large_button",
      ),
    }],
  });
  const provenance = document.querySelector("#review-provenance");
  selected.patient_supported_spans.forEach((span) => provenance.append(makeChip(t("patientSpan", { span }), "span-chip")));
  selected.ai_added_spans.forEach((span) => provenance.append(makeChip(t("aiSpan", { span }), "span-chip ai")));

  const readbackCheck = document.querySelector("#readback-check");
  const strictCheck = document.querySelector("#strict-check");
  const l3Check = document.querySelector("#l3-check");
  const confirm = document.querySelector("#final-confirm");

  const updateConfirm = () => {
    appState.readbackCompleted = readbackCheck.checked;
    const outstanding = [];
    if (!readbackCheck.checked) outstanding.push(t("outstandingReadback"));
    if (strict && !strictCheck.checked) outstanding.push(t("outstandingStrict"));
    if (l3 && !l3Check.checked) outstanding.push(t("outstandingL3"));
    const wasDisabled = confirm.disabled;
    confirm.disabled = outstanding.length > 0;
    // Say why the primary action is unavailable instead of only greying it out.
    setGate(
      confirm.disabled
        ? t("gateOutstanding", { items: outstanding.join(t("listSeparator")) })
        : t("gateReady"),
      !confirm.disabled,
    );
    if (wasDisabled && !confirm.disabled) {
      confirm.classList.remove("just-enabled");
      void confirm.offsetWidth;
      confirm.classList.add("just-enabled");
    }
  };
  readbackCheck.addEventListener("change", updateConfirm);
  strictCheck?.addEventListener("change", updateConfirm);
  l3Check?.addEventListener("change", updateConfirm);
  updateConfirm();

  document.querySelector("#edit-expression").addEventListener("click", editExpression);
  loadAudio("neutral", document.querySelector("#neutral-audio"));
}

/**
 * Earbud gestures, shown as information only.
 *
 * docs/06 keeps P0 on standard Bluetooth audio plus on-screen confirmation and
 * lists 耳机触控 under P1 ("官方 SDK 支持时"). It also states that an earphone
 * connection is neither identity nor consent, so no gesture is offered as the
 * thing that authorizes speech — the mapped actions are all reversible.
 */
function gestureHintMarkup() {
  const row = (tap, action) =>
    `<div class="gesture-row"><kbd>${escapeHtml(tap)}</kbd><span>${escapeHtml(action)}</span></div>`;
  return `
    <details class="gesture-hint">
      <summary aria-label="${escapeHtml(t("gestureInfoLabel"))}">${escapeHtml(t("gestureHintTitle"))}</summary>
      <div class="gesture-content">
        ${row(t("gestureTapOnce"), t("gestureRepeat"))}
        ${row(t("gestureTapTwice"), t("gestureBack"))}
        ${row(t("gestureHold"), t("gestureStop"))}
        <p class="capture-caption">${escapeHtml(t("gestureFootnote"))}</p>
      </div>
    </details>
  `;
}

function editExpression() {
  ui.editError.textContent = "";
  ui.editText.value = appState.model.selected_candidate?.text || "";
  ui.editDialog.showModal();
  ui.editText.focus();
  ui.editText.select();
}

function renderCompleted() {
  const selected = appState.model.selected_candidate;
  const receipt = appState.model.receipt;
  const primary = [{ label: t("startAnother"), onClick: () => createSession() }];
  renderStage({
    key: "completed",
    body: `
      <div class="result-headline">
        <div class="result-mark confirmed" aria-hidden="true">${icons.check}</div>
        <span class="eyebrow">${escapeHtml(t("completedEyebrow"))}</span>
        <h1 id="stage-title" class="stage-title">${escapeHtml(selected?.text || t("completedFallback"))}</h1>
      </div>
      <p class="lead">${escapeHtml(t("completedLead"))}</p>
      <div class="audio-review authorized">
        <strong>${escapeHtml(t("authorizedOutput"))}</strong>
        <span class="capture-caption">${escapeHtml(t("authorizedScope"))}</span>
        <audio id="personal-audio" controls preload="none" aria-label="${escapeHtml(t("authorizedOutput"))}"></audio>
      </div>
      ${receipt ? receiptMarkup(receipt) : ""}
      ${appState.lastAudioBlob ? `<div class="action-grid">
        <button id="compare-profile" class="button button-secondary" type="button">${escapeHtml(t("compareProfile"))}</button>
      </div>` : ""}
    `,
    primary,
  });
  loadAudio("personal", document.querySelector("#personal-audio"));
  document.querySelector("#compare-profile")?.addEventListener(
    "click",
    () => openProfileSetup({ replay: true }),
  );
}

function renderStopped() {
  renderStage({
    key: "stopped",
    body: `
      <div class="result-headline">
        <div class="result-mark halted" aria-hidden="true">${icons.halt}</div>
        <span class="eyebrow">${escapeHtml(t("stoppedEyebrow"))}</span>
        <h1 id="stage-title" class="stage-title">${escapeHtml(t("stoppedTitle"))}</h1>
        <p class="lead">${escapeHtml(t("stoppedLead"))}</p>
      </div>
    `,
    primary: [{ label: t("startNewSession"), onClick: () => createSession() }],
  });
}

function renderProcessing(stage) {
  renderStage({
    key: `processing:${stage}`,
    body: `
      <div class="loading-state">
        <span class="activity-indicator" aria-hidden="true"></span>
        <h1 id="stage-title" class="stage-title">${escapeHtml(stageLabelKeys[stage] ? stageLabel(stage) : t("stageProcessing"))}</h1>
      </div>
    `,
  });
}

function renderControls() {
  ui.controls.innerHTML = "";
  ui.stopSlot.innerHTML = "";
  const actions = new Set(appState.model.session.allowed_actions);
  if (actions.has("go_back")) addControl(t("back"), "go_back", ui.controls);
  if (actions.has("none_of_these")) addControl(t("noneOfThese"), "none_of_these", ui.controls);
  if (actions.has("switch_input_method")) addControl(t("switchInput"), "switch_input_method", ui.controls);
  // The native patient surface keeps the invariant controls visible. Help is
  // shown here only when it is the sole reversible path; when Back, None of
  // these, or Switch input are available, a fifth toolbar item would clip and
  // obscure those safety controls on compact iPhones.
  const hasNavigationControl = ["go_back", "none_of_these", "switch_input_method"]
    .some((action) => actions.has(action));
  if (actions.has("request_help") && !hasNavigationControl) {
    addControl(t("requestHelp"), "request_help", ui.controls);
  }
  // Stop lives outside the horizontal scroller so it can never scroll away.
  if (actions.has("stop")) addControl(t("stop"), "stop", ui.stopSlot, "button button-danger");
  markControlOverflow();
}

/** Flags the control row when it actually overflows, so CSS can fade its edge. */
function markControlOverflow() {
  requestAnimationFrame(() => {
    const overflowing = ui.controls.scrollWidth > ui.controls.clientWidth + 1;
    ui.controls.dataset.overflow = String(overflowing);
  });
}

function addControl(label, command, target, className = "button button-secondary") {
  const button = makeButton(label, className);
  button.dataset.command = command;
  // docs/06: Stop must stay available, including while a command is in flight.
  if (command === "stop") button.dataset.keepEnabled = "true";
  button.addEventListener("click", () => sendCommand(command));
  target.append(button);
}

/* ── Trace sheet ──────────────────────────────────────────────────────────── */

function openTrace() {
  if (ui.traceDialog.open) return;
  // Non-modal when docked so a presenter can drive the flow and watch events.
  if (dockedTrace.matches) ui.traceDialog.show();
  else ui.traceDialog.showModal();
  ui.traceButton.setAttribute("aria-expanded", "true");
}

function closeTrace() {
  if (ui.traceDialog.open) ui.traceDialog.close();
  ui.traceButton.setAttribute("aria-expanded", "false");
}

function renderTrace() {
  const events = appState.model.session.trace_items || [];
  ui.traceCount.textContent = events.length;
  updateTraceButtonLabel();
  ui.traceEmpty.hidden = events.length > 0;
  const freshCount = Math.max(0, events.length - appState.traceRendered);
  appState.traceRendered = events.length;
  const labels = eventLabels[appState.uiLanguage] || eventLabels.en;
  ui.trace.innerHTML = "";
  events.slice().reverse().forEach((event, index) => {
    const item = document.createElement("li");
    item.className = "trace-item";
    if (index < freshCount) item.dataset.fresh = "true";
    const marker = document.createElement("span");
    marker.className = "trace-marker";
    marker.setAttribute("aria-hidden", "true");
    const content = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = labels[event.event_type] || event.event_type;
    const detail = document.createElement("p");
    detail.textContent = traceDetail(event);
    content.append(title, detail);
    item.append(marker, content);
    ui.trace.append(item);
  });
}

function traceDetail(event) {
  const payload = event.payload || {};
  if (event.event_type === "ASR_RESULT_RECEIVED") {
    return t(payload.status === "success" ? "traceRecognitionSucceeded" : "traceRecognitionFailed");
  }
  if (event.event_type === "EVIDENCE_EXTRACTED") {
    return t("traceEvidenceCounts", {
      stable: (payload.stable_fragments || []).length,
      uncertain: (payload.uncertain_fragments || []).length,
    });
  }
  if (event.event_type === "MEMORY_RETRIEVED") {
    return t("traceVerifiedMemoryCount", { count: payload.verified_count || 0 });
  }
  if (event.event_type === "CONTEXT_RETRIEVED") {
    return t("traceContextMemoryCount", { count: payload.count || 0 });
  }
  if (event.event_type === "UNCERTAINTY_ASSESSED") {
    return uncertaintyRouteLabel(payload.effective_route);
  }
  if (event.event_type === "FINAL_CONFIRMATION_RECEIVED") {
    return t("traceFinalConfirmation", {
      method: confirmationMethodLabel(payload.method),
      level: payload.strict ? t("riskHigh") : t("riskOrdinary"),
    });
  }
  if (event.event_type === "VOICE_AUTHORIZATION_GRANTED") {
    return t("scopeThisExpression");
  }
  if (event.event_type === "VERIFIED_MEMORY_WRITTEN") {
    return t(payload.new_write ? "traceMemorySaved" : "traceMemoryUpdated");
  }
  return new Date(event.timestamp).toLocaleTimeString(
    appState.uiLanguage === "zh" ? "zh-CN" : "en-US",
    {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: appState.uiLanguage !== "zh",
    },
  );
}

async function loadAudio(kind, element) {
  if (!element || !appState.model.audio[`${kind}_available`]) {
    if (element) element.replaceWith(document.createTextNode(t("audioUnavailable")));
    return;
  }
  try {
    const response = await api(`/api/sessions/${appState.sessionId}/audio/${kind}`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    appState.audioUrls.push(url);
    element.src = url;
  } catch (error) {
    setStatus(error.message, "error");
  }
}

function receiptMarkup(receipt) {
  return `
    <h2>${escapeHtml(t("receiptHeading"))}</h2>
    <dl class="receipt-table">
      ${receiptRow(t("receiptConfirmation"), confirmationMethodLabel(receipt.confirmation_method))}
      ${receiptRow(t("receiptLevel"), sourceLevelLabel(receipt.expression_level))}
      ${receiptRow(t("receiptScope"), authorizationScopeLabel(receipt.authorization_scope))}
      ${receiptRow(t("receiptAiSpans"), receipt.ai_added_content.length ? receipt.ai_added_content.join(", ") : t("none"))}
      ${receiptRow(
        t("receiptMemory"),
        receipt.memory_ids_used.length
          ? t("memoryCount", { count: receipt.memory_ids_used.length })
          : t("none"),
      )}
    </dl>
    <details class="technical-details">
      <summary>${escapeHtml(t("receiptTechnical"))}</summary>
      <dl class="receipt-table compact">
        ${receiptRow(t("receiptHash"), `<code>${escapeHtml(receipt.final_text_hash.slice(0, 16))}…</code>`, true)}
      </dl>
    </details>
  `;
}

function receiptRow(label, value, isMarkup = false) {
  const body = isMarkup ? value : escapeHtml(String(value || t("none")));
  return `<div class="receipt-row"><dt>${escapeHtml(label)}</dt><dd>${body}</dd></div>`;
}

function tokenGroup(label, values, uncertain) {
  return `
    <div class="evidence-group">
      <span class="evidence-label">${escapeHtml(label)}</span>
      <div class="token-row">${values.map((value, index) => `<span class="token ${uncertain ? "uncertain" : ""}" style="--i:${index}">${escapeHtml(value)}</span>`).join("")}</div>
    </div>
  `;
}

function heardSequenceMarkup() {
  const sequence = appState.model.session.heard_sequence || [];
  if (!sequence.length) {
    const stable = appState.model.session.heard_stable || [];
    const uncertain = appState.model.session.heard_uncertain || [];
    return `
      ${tokenGroup(t("stableFragments"), stable, false)}
      ${uncertain.length ? tokenGroup(t("uncertainFragments"), uncertain, true) : ""}
    `;
  }
  return `
    <p class="heard-sentence" role="group" aria-label="${escapeHtml(t("heardSentenceAria"))}">
      ${sequence.map((token, index) => `
        <span class="heard-word ${token.status === "uncertain" ? "uncertain" : "stable"}"
          style="--i:${index}">${escapeHtml(token.text)}</span>
      `).join("")}
    </p>
  `;
}

function infoDisclosureMarkup(label, title, body, className = "") {
  return `
    <details class="info-disclosure ${escapeHtml(className)}">
      <summary aria-label="${escapeHtml(label)}"><span aria-hidden="true">i</span></summary>
      <div class="info-card" role="note">
        <strong>${escapeHtml(title)}</strong>
        <p>${escapeHtml(body)}</p>
      </div>
    </details>
  `;
}

function makeButton(label, className) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.textContent = label;
  return button;
}

function makeChip(label, className) {
  const chip = document.createElement("span");
  chip.className = className;
  chip.textContent = label;
  return chip;
}

function riskLabel(value) {
  if (value === "high_risk") return t("riskHigh");
  if (value === "sensitive") return t("riskSensitive");
  return t("riskOrdinary");
}

function sourceLevelLabel(value) {
  if (value === "L1") return t("sourceL1");
  if (value === "L3") return t("sourceL3");
  return t("sourceL2");
}

function sourceInfoTitle(value) {
  if (value === "L1") return t("sourceL1InfoTitle");
  if (value === "L3") return t("sourceL3InfoTitle");
  return t("sourceL2InfoTitle");
}

function sourceInfoBody(value) {
  if (value === "L1") return t("sourceL1InfoBody");
  if (value === "L3") return t("sourceL3InfoBody");
  return t("sourceL2InfoBody");
}

function riskInfoTitle(value) {
  if (value === "high_risk") return t("riskHighInfoTitle");
  if (value === "sensitive") return t("riskSensitiveInfoTitle");
  return t("riskOrdinaryInfoTitle");
}

function riskInfoBody(value) {
  if (value === "high_risk") return t("riskHighInfoBody");
  if (value === "sensitive") return t("riskSensitiveInfoBody");
  return t("riskOrdinaryInfoBody");
}

function confirmationMethodLabel(value) {
  const labels = {
    large_button: "confirmationLargeButton",
    keyboard: "confirmationKeyboard",
    scanning: "confirmationScanning",
    dwell: "confirmationDwell",
    second_method: "confirmationSecondMethod",
  };
  return t(labels[value] || "confirmationLargeButton");
}

function authorizationScopeLabel(value) {
  return value === "this_expression" ? t("scopeThisExpression") : t("none");
}

function uncertaintyRouteLabel(value) {
  if (value === "high_uncertainty") return t("traceNeedsClarification");
  if (value === "low_uncertainty") return t("traceReadyForFinalReview");
  return t("traceNeedsChoices");
}

function voiceLabel(value) {
  if (value === "used") return t("voiceUsed");
  if (value === "authorized") return t("voiceAuthorized");
  if (value === "awaiting_confirmation") return t("voiceAwaiting");
  return t("voiceBlocked");
}

function showLoading(message) {
  appState.stageKey = "loading";
  stopWaveform();
  setGate("");
  ui.primaryActions.innerHTML = "";
  ui.decision.innerHTML = `
    <div class="stage loading-state">
      <span class="activity-indicator" aria-hidden="true"></span>
      <p>${escapeHtml(message)}</p>
    </div>
  `;
}

function setStatus(message, tone = "error") {
  ui.status.textContent = message || "";
  if (message) ui.status.dataset.tone = tone;
  else delete ui.status.dataset.tone;
}

function setGate(message, ready = false) {
  ui.gate.textContent = message || "";
  ui.gate.dataset.ready = String(Boolean(ready));
}

function showFatal(message) {
  renderStage({
    key: "fatal",
    body: `
      <span class="eyebrow">${escapeHtml(t("fatalEyebrow"))}</span>
      <h1 id="stage-title" class="stage-title">${escapeHtml(t("fatalTitle"))}</h1>
      <p class="lead">${escapeHtml(message)}</p>
    `,
  });
}

/**
 * Marks the workspace busy during a command.
 *
 * Only elements this function disabled are re-enabled, so a control that was
 * deliberately disabled by its own stage — above all "Confirm and speak"
 * before the patient has checked the readback boxes — is never switched on as
 * a side effect of a request finishing.
 */
function setInteractionDisabled(disabled) {
  ui.workspace.setAttribute("aria-busy", String(disabled));
  document.querySelectorAll("button, input, select, textarea").forEach((element) => {
    if (element.closest("dialog")) return;
    if (element.dataset.keepEnabled === "true") return;
    if (disabled) {
      if (!element.disabled) {
        element.dataset.busyDisabled = "true";
        element.disabled = true;
      }
      return;
    }
    if (element.dataset.busyDisabled === "true") {
      delete element.dataset.busyDisabled;
      element.disabled = false;
    }
  });
}

function startRecordingTimer() {
  stopRecordingTimer();
  appState.recordingAutoStopStarted = false;
  appState.recordingTimer = window.setInterval(updateCaptureClock, 250);
}

function stopRecordingTimer() {
  if (appState.recordingTimer) window.clearInterval(appState.recordingTimer);
  appState.recordingTimer = null;
}

function updateCaptureClock() {
  const target = document.querySelector("#capture-time");
  if (!target || !appState.recordingStartedAt) return;
  const elapsedSeconds = (Date.now() - appState.recordingStartedAt) / 1000;
  const seconds = Math.floor(elapsedSeconds);
  target.textContent = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  if (
    elapsedSeconds >= Math.max(
      0.1,
      appState.maxAudioSeconds - RECORDING_STOP_HEADROOM_SECONDS,
    )
    && appState.recorder
    && !appState.recordingAutoStopStarted
  ) {
    appState.recordingAutoStopStarted = true;
    setStatus(t("maxRecordingReached", { seconds: appState.maxAudioSeconds }), "info");
    void stopMicrophone();
  }
}

function clearAudioUrls() {
  appState.audioUrls.forEach((url) => URL.revokeObjectURL(url));
  appState.audioUrls = [];
}

function escapeHtml(value) {
  const span = document.createElement("span");
  span.textContent = String(value ?? "");
  return span.innerHTML;
}

/* ── Global input ─────────────────────────────────────────────────────────── */

// Number keys pick a candidate on a hardware keyboard. Selection only — no key
// ever confirms or speaks.
document.addEventListener("keydown", (event) => {
  if (event.metaKey || event.ctrlKey || event.altKey) return;
  if (document.querySelector("dialog[open]:modal")) return;
  const tag = event.target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
  if (!/^[1-9]$/.test(event.key)) return;
  const list = document.querySelector("#candidate-list");
  if (!list) return;
  const target = list.querySelector(
    `.candidate-select[data-candidate-index="${Number(event.key) - 1}"]`,
  );
  if (!target || target.disabled) return;
  event.preventDefault();
  target.focus();
  target.click();
});

ui.languageToggle.addEventListener("click", () => {
  setLanguage(appState.uiLanguage === "en" ? "zh" : "en", { pin: true });
});

ui.appearanceSelect.addEventListener("change", (event) => {
  setAppearance(event.target.value);
});

systemDarkAppearance.addEventListener("change", () => {
  if (appState.appearance === "auto") applyAppearance();
});

ui.traceButton.addEventListener("click", () => {
  if (ui.traceDialog.open) closeTrace();
  else openTrace();
});

ui.traceClose.addEventListener("click", closeTrace);

// Esc and backdrop dismissal both fire close, so keep the trigger in sync.
ui.traceDialog.addEventListener("close", () => {
  ui.traceButton.setAttribute("aria-expanded", "false");
});

// Crossing the dock breakpoint changes modal vs non-modal, so reopen in the
// right mode rather than leaving a modal sheet docked in the layout.
dockedTrace.addEventListener("change", () => {
  if (!ui.traceDialog.open) {
    if (dockedTrace.matches) openTrace();
    return;
  }
  ui.traceDialog.close();
  openTrace();
});

ui.accessForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  appState.demoToken = ui.accessCode.value;
  sessionStorage.setItem("meantbyme_demo_token", appState.demoToken);
  ui.accessError.textContent = "";
  ui.accessDialog.close();
  await openProfileSetup();
});

ui.profileForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const option = ui.profileSelect.selectedOptions[0];
  if (!option) return;
  appState.profileRef = option.value;
  appState.profileLanguage = option.dataset.language || "en";
  // The profile suggests the interface language until the patient pins one.
  if (!appState.languagePinned) {
    setLanguage(suggestedInterfaceLanguage(option));
  }
  ui.profileDialog.close();
  await createSession();
});

ui.profileInput.addEventListener("change", async (event) => {
  const [file] = event.target.files;
  if (!file) return;
  ui.profileError.textContent = "";
  try {
    const response = await api("/api/profiles", {
      method: "POST",
      headers: { "Content-Type": "text/markdown" },
      body: file,
    });
    const payload = await response.json();
    renderProfileOptions(payload.profile);
    ui.profileSelect.value = payload.profile.profile_ref;
  } catch (error) {
    ui.profileError.textContent = error.message;
  } finally {
    event.target.value = "";
  }
});

ui.profileButton.addEventListener("click", () => openProfileSetup());

ui.editCancel.addEventListener("click", () => ui.editDialog.close());

ui.editForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = ui.editText.value.trim();
  if (!text) {
    ui.editError.textContent = t("editEmpty");
    return;
  }
  ui.editDialog.close();
  appState.readbackCompleted = false;
  await sendCommand("edit_completion", { text });
});

/* ── Microphone capture ───────────────────────────────────────────────────── */

class BrowserWavRecorder {
  constructor(stream, context, source, processor, analyser) {
    this.stream = stream;
    this.context = context;
    this.source = source;
    this.processor = processor;
    this.analyser = analyser;
    this.timeDomain = analyser ? new Uint8Array(analyser.fftSize) : null;
    this.buffers = [];
    this.recording = false;
  }

  static async create() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const context = new AudioContext();
    const source = context.createMediaStreamSource(stream);
    const processor = context.createScriptProcessor(4096, 1, 1);
    const analyser = context.createAnalyser();
    analyser.fftSize = 1024;
    analyser.smoothingTimeConstant = 0.7;
    const recorder = new BrowserWavRecorder(stream, context, source, processor, analyser);
    processor.onaudioprocess = (event) => {
      if (recorder.recording) {
        recorder.buffers.push(new Float32Array(event.inputBuffer.getChannelData(0)));
      }
    };
    source.connect(analyser);
    source.connect(processor);
    processor.connect(context.destination);
    return recorder;
  }

  /** Per-bar microphone amplitude in 0..1, tapered so it reads as one shape. */
  readLevels(bars) {
    if (!this.analyser || !this.recording) return null;
    this.analyser.getByteTimeDomainData(this.timeDomain);
    const width = Math.floor(this.timeDomain.length / bars);
    const levels = new Array(bars);
    for (let bar = 0; bar < bars; bar += 1) {
      let energy = 0;
      for (let offset = 0; offset < width; offset += 1) {
        const sample = (this.timeDomain[bar * width + offset] - 128) / 128;
        energy += sample * sample;
      }
      const rms = Math.sqrt(energy / width);
      const taper = 0.55 + 0.45 * Math.sin(((bar + 0.5) / bars) * Math.PI);
      levels[bar] = Math.min(1, rms * 3.4 * taper);
    }
    return levels;
  }

  start() {
    this.recording = true;
  }

  async stop() {
    this.recording = false;
    const merged = mergeBuffers(this.buffers);
    const downsampled = downsample(merged, this.context.sampleRate, 16000);
    await this.cleanup();
    return encodeWav(downsampled, 16000);
  }

  async cancel() {
    this.recording = false;
    await this.cleanup();
  }

  async cleanup() {
    this.processor.disconnect();
    this.source.disconnect();
    this.analyser?.disconnect();
    this.stream.getTracks().forEach((track) => track.stop());
    await this.context.close();
  }
}

function mergeBuffers(buffers) {
  const length = buffers.reduce((total, buffer) => total + buffer.length, 0);
  const merged = new Float32Array(length);
  let offset = 0;
  buffers.forEach((buffer) => {
    merged.set(buffer, offset);
    offset += buffer.length;
  });
  return merged;
}

function downsample(input, inputRate, outputRate) {
  if (inputRate === outputRate) return input;
  const ratio = inputRate / outputRate;
  const output = new Float32Array(Math.floor(input.length / ratio));
  for (let index = 0; index < output.length; index += 1) {
    const start = Math.floor(index * ratio);
    const end = Math.min(Math.floor((index + 1) * ratio), input.length);
    let sum = 0;
    for (let cursor = start; cursor < end; cursor += 1) sum += input[cursor];
    output[index] = sum / Math.max(1, end - start);
  }
  return output;
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  writeAscii(view, 0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeAscii(view, 8, "WAVE");
  writeAscii(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeAscii(view, 36, "data");
  view.setUint32(40, samples.length * 2, true);
  samples.forEach((sample, index) => {
    const clamped = Math.max(-1, Math.min(1, sample));
    view.setInt16(44 + index * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
  });
  return new Blob([view], { type: "audio/wav" });
}

function writeAscii(view, offset, text) {
  for (let index = 0; index < text.length; index += 1) {
    view.setUint8(offset + index, text.charCodeAt(index));
  }
}

setupLaunchScreen();
initialize();
