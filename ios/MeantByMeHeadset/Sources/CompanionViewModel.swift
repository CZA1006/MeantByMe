import Combine
import Foundation

@MainActor
final class CompanionViewModel: ObservableObject {
    @Published var mode: CompanionMode = .expression
    @Published private(set) var sessionStarted = false
    @Published private(set) var sessionStatus = "等待陪护者开始"
    @Published private(set) var safetyStatus = "患者声音未授权"
    @Published var errorMessage: String?

    let headset = ViaimHeadsetService()
    private let audioRouter = AudioRouter()
    private var gateway: GatewayClient?
    private var response: DemoResponse?
    private var stopTask: Task<Void, Never>?
    private var promptContext: PromptContext = .none
    private var currentPromptID = ""
    private var candidateIndex = 0

    var headsetConnected: Bool { headset.connected }
    var headsetStatus: String { headset.status }

    init() {
        do {
            gateway = try GatewayClient()
        } catch {
            errorMessage = error.localizedDescription
        }
        headset.onPrimaryFinal = { [weak self] _, purpose in
            self?.scheduleCaptureStop(purpose)
        }
        headset.onCaptureFinished = { [weak self] capture in
            Task { await self?.handleCapture(capture) }
        }
        headset.onSafetyInterruption = { [weak self] reason in
            self?.abortForHardwareSafety(reason)
        }
        headset.objectWillChange.sink { [weak self] _ in
            self?.objectWillChange.send()
        }.store(in: &cancellables)
    }

    private var cancellables: Set<AnyCancellable> = []

    func connectHeadset() {
        headset.initializeAndConnect()
    }

    func startCompanion() async {
        guard let gateway, headset.connected else { return }
        guard mode == .expression else {
            errorMessage = "当前队友后端尚未提供问答接口，本版本先完成“替患者表达”真机链路。"
            return
        }
        do {
            let created = try await gateway.createSession()
            response = created
            sessionStarted = true
            sessionStatus = "会话已开始，正在等待患者表达"
            safetyStatus = "所有候选只在耳机中私密朗读"
            let capturing = try await gateway.command("start_capture")
            response = capturing
            headset.startCapture(.expression)
        } catch {
            fail(error)
        }
    }

    func stopCompanion() async {
        stopTask?.cancel()
        audioRouter.stop()
        headset.stopCapture()
        if let gateway {
            _ = try? await gateway.command("stop")
        }
        sessionStarted = false
        sessionStatus = "会话已结束"
        safetyStatus = "患者声音未授权"
    }

    private func scheduleCaptureStop(_ purpose: CapturePurpose) {
        stopTask?.cancel()
        stopTask = Task {
            let delay: UInt64 = purpose == .expression ? 2_500_000_000 : 900_000_000
            try? await Task.sleep(nanoseconds: delay)
            guard !Task.isCancelled else { return }
            headset.stopCapture()
        }
    }

    private func handleCapture(_ capture: EarbudCapture) async {
        guard !capture.pcm.isEmpty, let gateway else {
            errorMessage = "没有收到耳机麦克风 PCM，未执行任何确认。"
            return
        }
        let wav = WAVEncoder.pcm16Mono16k(capture.pcm)
        do {
            switch capture.purpose {
            case .expression:
                sessionStatus = "正在理解患者表达…"
                try await gateway.uploadExpression(
                    wav: wav,
                    primaryTranscript: capture.primaryTranscript
                )
                response = try await gateway.command("stop_capture")
                try await drivePrivateFlow()
            case .command:
                guard !capture.primaryTranscript.isEmpty else {
                    try await repeatCurrentPrompt("没有听清，请再说一次。")
                    return
                }
                let interpretation = try await gateway.interpretCommand(
                    wav: wav,
                    primaryTranscript: capture.primaryTranscript
                )
                try await apply(
                    interpretation: interpretation,
                    rawTranscript: capture.primaryTranscript
                )
            }
        } catch {
            fail(error)
        }
    }

    private func drivePrivateFlow() async throws {
        guard let response, let gateway else { return }
        switch response.session.stage {
        case "heard_content_review":
            promptContext = .heard
            let fragments = response.session.heardStable.joined(separator: "，")
            try privateSpeak("我听到的是：\(fragments)。如果正确，请说是；不正确请说不是。")
        case "category_clarification":
            promptContext = .category(response.session.clarificationOptions)
            let question = response.session.clarificationQuestion ?? "这句话属于哪一类？"
            try privateSpeak(
                question + "。选项是：" + response.session.clarificationOptions.joined(separator: "，")
            )
        case "candidate_selection", "final_review":
            if let selected = response.selectedCandidate {
                promptContext = .final(selected)
                let audio = try await gateway.audio(kind: "neutral")
                try privateAudio(audio)
            } else {
                guard !response.session.candidates.isEmpty else {
                    throw GatewayClientError.invalidResponse
                }
                candidateIndex = min(candidateIndex, response.session.candidates.count - 1)
                let candidate = response.session.candidates[candidateIndex]
                promptContext = .candidate(candidate)
                try privateSpeak(
                    "候选表达：\(candidate.text)。如果符合你的意思，请说是；换一个请说不是；重听请说再说一次。"
                )
            }
        case "voice_authorized":
            safetyStatus = "已获得患者确认，准备通过手机扬声器播放"
            let personal = try await gateway.audio(kind: "personal")
            let playbackID = UUID().uuidString
            headset.stopCapture()
            try audioRouter.playPublicAudio(personal) { [weak self] success in
                Task { @MainActor in
                    guard let self, let gateway = self.gateway else { return }
                    do {
                        self.response = try await gateway.command(
                            success ? "playback_completed" : "playback_failed",
                            payload: [
                                "playback_id": playbackID,
                                "output_channel": "iphone_speaker",
                            ]
                        )
                        self.sessionStatus = success
                            ? "表达已播放完成"
                            : "播放失败，未写入回执或确认记忆"
                        self.safetyStatus = success
                            ? "已收到播放完成回执，本次一次性表达已完成"
                            : "请由陪护者检查手机扬声器后重试"
                    } catch {
                        self.fail(error)
                    }
                }
            }
        case "completed":
            sessionStatus = "表达已播放完成"
            safetyStatus = "已收到播放完成回执，本次一次性表达已完成"
        case "stopped":
            sessionStatus = "患者已停止本次会话"
            sessionStarted = false
        default:
            sessionStatus = "处理中：\(response.session.stage)"
        }
    }

    private func apply(
        interpretation: EarbudInterpretation,
        rawTranscript: String
    ) async throws {
        guard let gateway else { return }
        if interpretation.intent == "stop" {
            response = try await gateway.command("stop")
            try await drivePrivateFlow()
            return
        }
        switch promptContext {
        case .heard:
            if interpretation.intent == "affirm" && interpretation.consensus {
                response = try await gateway.command("confirm_heard_content")
                candidateIndex = 0
                try await drivePrivateFlow()
            } else if interpretation.intent == "reject" {
                response = try await gateway.command("reject_heard_content")
                sessionStatus = "患者否定了识别结果，本次不会使用"
            } else {
                try await repeatCurrentPrompt("我没有听清确认结果。")
            }
        case let .category(options):
            if let option = options.first(where: {
                rawTranscript.localizedCaseInsensitiveContains($0)
            }) {
                response = try await gateway.command(
                    "select_category",
                    payload: ["category": option]
                )
                try await drivePrivateFlow()
            } else {
                try await repeatCurrentPrompt("没有听清类别，请再说一次。")
            }
        case let .candidate(candidate):
            if interpretation.intent == "affirm" && interpretation.consensus {
                response = try await gateway.command(
                    "select_candidate",
                    payload: ["candidate_id": candidate.id]
                )
                try await drivePrivateFlow()
            } else if interpretation.intent == "reject" {
                candidateIndex += 1
                if let response, candidateIndex < response.session.candidates.count {
                    try await drivePrivateFlow()
                } else {
                    response = try await gateway.command("none_of_these")
                    candidateIndex = 0
                    try await drivePrivateFlow()
                }
            } else {
                try await repeatCurrentPrompt("我会再读一次。")
            }
        case let .final(candidate):
            if interpretation.intent == "affirm" && interpretation.consensus {
                let strict = response?.strict ?? false
                let l3 = candidate.sourceLevel == "L3"
                if strict || l3 {
                    let firstPromptID = currentPromptID
                    promptContext = .additionalFinal(
                        candidate,
                        firstPromptID: firstPromptID,
                        firstAudioHash: interpretation.audioInputHash
                    )
                    try privateSpeak(
                        "这是需要额外确认的表达：\(candidate.text)。"
                        + "如果这仍然准确表达你的意思，请再次明确回答。"
                    )
                } else {
                    try await submitFinalConfirmation(
                        candidate,
                        strict: false,
                        evidence: nil
                    )
                }
            } else if interpretation.intent == "reject" {
                response = try await gateway.command("go_back")
                candidateIndex = 0
                try await drivePrivateFlow()
            } else {
                try await repeatCurrentPrompt("我会重新完整朗读。")
            }
        case let .additionalFinal(
            candidate,
            firstPromptID,
            firstAudioHash
        ):
            if interpretation.intent == "affirm" && interpretation.consensus {
                guard
                    firstPromptID != currentPromptID,
                    firstAudioHash != interpretation.audioInputHash
                else {
                    try await repeatCurrentPrompt(
                        "两次确认证据不能相同，请再次回答。"
                    )
                    return
                }
                try await submitFinalConfirmation(
                    candidate,
                    strict: response?.strict ?? false,
                    evidence: [
                        "first_prompt_id": firstPromptID,
                        "second_prompt_id": currentPromptID,
                        "first_audio_hash": firstAudioHash,
                        "second_audio_hash": interpretation.audioInputHash,
                    ]
                )
            } else if interpretation.intent == "reject" {
                response = try await gateway.command("go_back")
                candidateIndex = 0
                try await drivePrivateFlow()
            } else {
                try await repeatCurrentPrompt("请再次明确确认或否定。")
            }
        case .none:
            break
        }
    }

    private func submitFinalConfirmation(
        _ candidate: Candidate,
        strict: Bool,
        evidence: [String: Any]?
    ) async throws {
        guard let gateway else { return }
        var payload: [String: Any] = [
            "private_readback_completed": true,
            "strict_confirmation": strict,
            "l3_confirmation": candidate.sourceLevel == "L3",
        ]
        if let evidence {
            payload["voice_confirmation_evidence"] = evidence
        }
        response = try await gateway.command(
            "final_confirm",
            payload: payload,
            confirmationMethod: "voice_semantic"
        )
        try await drivePrivateFlow()
    }

    private func repeatCurrentPrompt(_ prefix: String) async throws {
        sessionStatus = prefix
        try await drivePrivateFlow()
    }

    private func privateSpeak(_ text: String) throws {
        currentPromptID = UUID().uuidString
        safetyStatus = "未确认内容仅通过耳机中性音朗读"
        headset.stopCapture()
        try audioRouter.playPrivateText(text, language: "zh-CN") { [weak self] success in
            Task { @MainActor in
                guard let self else { return }
                if success {
                    self.sessionStatus = "等待患者语音回应"
                    self.headset.startCapture(.command)
                } else {
                    self.errorMessage = "私密朗读失败；不会执行确认。"
                }
            }
        }
    }

    private func privateAudio(_ data: Data) throws {
        currentPromptID = UUID().uuidString
        safetyStatus = "患者声音仍被阻止；正在耳机中完整复核"
        headset.stopCapture()
        try audioRouter.playPrivateAudio(data) { [weak self] success in
            Task { @MainActor in
                guard let self else { return }
                if success {
                    self.sessionStatus = "等待患者最终确认"
                    self.headset.startCapture(.command)
                } else {
                    self.errorMessage = "完整私密复核未完成；不会授权患者声音。"
                }
            }
        }
    }

    private func fail(_ error: Error) {
        errorMessage = error.localizedDescription
        sessionStatus = "发生错误，未执行确认或外放"
        safetyStatus = "患者声音未授权"
    }

    private func abortForHardwareSafety(_ reason: String) {
        stopTask?.cancel()
        audioRouter.stop()
        sessionStarted = false
        sessionStatus = "\(reason)，本次会话已安全停止"
        safetyStatus = "未执行新的确认、外放或记忆写入"
        Task {
            if let gateway {
                _ = try? await gateway.command("stop")
            }
        }
    }
}

private enum PromptContext {
    case none
    case heard
    case category([String])
    case candidate(Candidate)
    case final(Candidate)
    case additionalFinal(
        Candidate,
        firstPromptID: String,
        firstAudioHash: String
    )
}
