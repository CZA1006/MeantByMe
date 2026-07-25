import Combine
import Foundation

@MainActor
final class CompanionViewModel: ObservableObject {
    @Published var mode: CompanionMode = .expression
    @Published private(set) var sessionStarted = false
    @Published private(set) var sessionStatus = "等待陪护者开始"
    @Published private(set) var safetyStatus = "仅使用系统中性音"
    @Published private(set) var expressionElapsedSeconds = 0
    @Published private(set) var expressionTimerActive = false
    @Published private(set) var expressionTimerVisible = false
    @Published var speakerVolumeTestPresented = false
    @Published var userSettingsPresented = false
    @Published private(set) var profiles: [UserProfileSummary] = []
    @Published private(set) var selectedProfileRef: String
    @Published private(set) var selectedProfileLabel: String
    @Published private(set) var selectedProfileLanguage: String
    @Published private(set) var selectedProfileDetail: UserProfileDetail?
    @Published private(set) var profilesLoading = false
    @Published var errorMessage: String?

    let headset = ViaimHeadsetService()
    private let audioRouter = AudioRouter()
    private var gateway: GatewayClient?
    private var response: DemoResponse?
    private var silenceTask: Task<Void, Never>?
    private var expressionTimerTask: Task<Void, Never>?
    private var captureProcessingTask: Task<Void, Never>?
    private var safetyAbortInProgress = false
    private var captureBoundaryReached = false
    private var activeSessionID: String?
    private var stoppedSessionRecoveryAttempted = false
    private var currentCandidate: Candidate?
    private var privateReadbackCompleted = false
    private var additionalVoiceConfirmationRequired = false
    private var firstConfirmationEvidence: VoiceCommandEvidence?
    private var currentPromptID = ""
    private var cancellables: Set<AnyCancellable> = []

    var headsetConnected: Bool { headset.connected }
    var headsetStatus: String { headset.status }
    var canEditCurrentUser: Bool { !sessionStarted }

    init() {
        let defaults = UserDefaults.standard
        selectedProfileRef = defaults.string(
            forKey: "selected_profile_ref"
        ) ?? "lin_yue_demo"
        selectedProfileLabel = defaults.string(
            forKey: "selected_profile_label"
        ) ?? "Lin Yue（演示用户）"
        selectedProfileLanguage = defaults.string(
            forKey: "selected_profile_language"
        ) ?? "zh"
        do {
            gateway = try GatewayClient()
        } catch {
            errorMessage = error.localizedDescription
        }
        headset.onSpeechActivity = { [weak self] purpose in
            self?.scheduleSilenceBoundary(purpose)
        }
        headset.onCaptureFinished = { [weak self] capture in
            guard let self else { return }
            self.captureProcessingTask?.cancel()
            self.captureProcessingTask = Task {
                await self.handleCapture(capture)
            }
        }
        headset.onSafetyInterruption = { [weak self] reason in
            self?.abortForHardwareSafety(reason)
        }
        headset.objectWillChange.sink { [weak self] _ in
            self?.objectWillChange.send()
        }.store(in: &cancellables)
        Task { [weak self] in
            await self?.refreshProfiles()
        }
    }

    func connectHeadset() {
        headset.initializeAndConnect()
    }

    func refreshProfiles() async {
        guard let gateway, !profilesLoading else { return }
        profilesLoading = true
        defer { profilesLoading = false }
        do {
            let loaded = try await gateway.listProfiles()
            profiles = loaded
            if !sessionStarted {
                if let selected = loaded.first(where: {
                    $0.profileRef == selectedProfileRef
                }) {
                    applySelectedProfile(selected)
                } else if let fallback = loaded.first(where: {
                    $0.profileRef == "lin_yue_demo"
                }) ?? loaded.first {
                    applySelectedProfile(fallback)
                }
            }
            await loadSelectedProfileDetail()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func selectProfile(_ profileRef: String) async {
        guard !sessionStarted else { return }
        guard let profile = profiles.first(where: {
            $0.profileRef == profileRef
        }) else { return }
        applySelectedProfile(profile)
        await loadSelectedProfileDetail()
    }

    func loadSelectedProfileDetail() async {
        guard let gateway else { return }
        do {
            selectedProfileDetail = try await gateway.profileDetail(
                profileRef: selectedProfileRef
            )
        } catch {
            selectedProfileDetail = nil
            errorMessage = error.localizedDescription
        }
    }

    func createUserProfile(
        _ input: NewUserProfileInput
    ) async -> Bool {
        guard let gateway, !sessionStarted else { return false }
        do {
            let created = try await gateway.createProfile(input)
            profiles = try await gateway.listProfiles()
            applySelectedProfile(created)
            await loadSelectedProfileDetail()
            return true
        } catch {
            errorMessage = error.localizedDescription
            return false
        }
    }

    func importUserProfileMarkdown(_ data: Data) async -> Bool {
        guard let gateway, !sessionStarted else { return false }
        do {
            let created = try await gateway.importProfileMarkdown(data)
            profiles = try await gateway.listProfiles()
            applySelectedProfile(created)
            await loadSelectedProfileDetail()
            return true
        } catch {
            errorMessage = error.localizedDescription
            return false
        }
    }

    private func applySelectedProfile(_ profile: UserProfileSummary) {
        selectedProfileRef = profile.profileRef
        selectedProfileLabel = profile.label
        selectedProfileLanguage = profile.defaultLanguage
        let defaults = UserDefaults.standard
        defaults.set(profile.profileRef, forKey: "selected_profile_ref")
        defaults.set(profile.label, forKey: "selected_profile_label")
        defaults.set(
            profile.defaultLanguage,
            forKey: "selected_profile_language"
        )
    }

    func beginSpeakerVolumeTest() async {
        guard !sessionStarted else { return }
        do {
            try await audioRouter.beginSpeakerVolumeTest()
            speakerVolumeTestPresented = true
            try audioRouter.playSpeakerVolumeTest()
        } catch {
            audioRouter.endSpeakerVolumeTest()
            errorMessage = error.localizedDescription
        }
    }

    func repeatSpeakerVolumeTest() {
        do {
            try audioRouter.playSpeakerVolumeTest()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func endSpeakerVolumeTest() {
        audioRouter.endSpeakerVolumeTest()
        speakerVolumeTestPresented = false
    }

    func startCompanion() async {
        guard gateway != nil, headset.connected else { return }
        guard !sessionStarted, !safetyAbortInProgress else { return }
        guard mode == .expression else {
            errorMessage = "问答模式尚未接入；本版本先实现“替患者表达”。"
            return
        }
        endSpeakerVolumeTest()
        sessionStarted = true
        safetyStatus = "候选仅在耳机播放；语音确认后以中性音外放"
        do {
            try await beginNextExpressionRound()
        } catch {
            fail(error)
        }
    }

    func stopCompanion() async {
        guard !safetyAbortInProgress else { return }
        safetyAbortInProgress = true
        let sessionIDToStop = activeSessionID
        silenceTask?.cancel()
        stopExpressionTimer(reset: true)
        captureProcessingTask?.cancel()
        activeSessionID = nil
        sessionStatus = "正在结束陪伴并丢弃未完成的表达…"
        audioRouter.stop()
        headset.stopCapture()
        if let gateway, let sessionIDToStop {
            _ = try? await gateway.command(
                "stop",
                expectedSessionID: sessionIDToStop
            )
        }
        sessionStarted = false
        safetyAbortInProgress = false
        resetRoundState()
        sessionStatus = "陪伴已结束"
        safetyStatus = "仅使用系统中性音"
    }

    private func beginNextExpressionRound() async throws {
        guard let gateway, sessionStarted, !safetyAbortInProgress else {
            return
        }
        silenceTask?.cancel()
        stopExpressionTimer(reset: true)
        captureProcessingTask?.cancel()
        resetRoundState()
        activeSessionID = nil
        let created = try await gateway.createSession(
            language: selectedProfileLanguage,
            profileRef: selectedProfileRef
        )
        response = created
        activeSessionID = created.session.sessionId
        stoppedSessionRecoveryAttempted = false
        response = try await gateway.command("start_capture")
        sessionStatus = "正在持续聆听；停顿 8 秒后自动理解本次表达"
        captureBoundaryReached = false
        headset.startCapture(
            .expression,
            sessionID: created.session.sessionId
        )
    }

    private func scheduleSilenceBoundary(_ purpose: CapturePurpose) {
        guard
            sessionStarted,
            !safetyAbortInProgress,
            !captureBoundaryReached
        else {
            return
        }
        silenceTask?.cancel()
        let delay: UInt64
        switch purpose {
        case .expression:
            startExpressionTimerIfNeeded()
            delay = 8_000_000_000
            sessionStatus = "检测到患者说话；继续说话会重新计算 8 秒"
        case .command:
            delay = 1_200_000_000
            sessionStatus = "正在聆听患者的确认或否定…"
        }
        silenceTask = Task {
            try? await Task.sleep(nanoseconds: delay)
            guard !Task.isCancelled else { return }
            captureBoundaryReached = true
            if purpose == .expression {
                stopExpressionTimer(reset: false)
            }
            sessionStatus = purpose == .expression
                ? "已静默 8 秒，正在结束本次表达…"
                : "正在理解患者的语音回应…"
            headset.stopCapture()
        }
    }

    private func handleCapture(_ capture: EarbudCapture) async {
        guard !Task.isCancelled else { return }
        guard sessionStarted, !safetyAbortInProgress else { return }
        guard capture.sessionID == activeSessionID else { return }
        if capture.purpose == .expression {
            stopExpressionTimer(reset: false)
        }
        guard !capture.pcm.isEmpty else {
            await restartAfterEmptyCapture(capture.purpose)
            return
        }
        let wav = WAVEncoder.pcm16Mono16k(capture.pcm)
        do {
            switch capture.purpose {
            case .expression:
                try await submitExpressionCapture(
                    wav: wav,
                    primaryTranscript: capture.primaryTranscript
                )
            case .command:
                try await submitVoiceCommand(
                    wav: wav,
                    primaryTranscript: capture.primaryTranscript
                )
            }
        } catch {
            guard
                !Task.isCancelled,
                capture.sessionID == activeSessionID,
                sessionStarted,
                !safetyAbortInProgress
            else {
                return
            }
            fail(error)
        }
    }

    private func submitExpressionCapture(
        wav: Data,
        primaryTranscript: String
    ) async throws {
        guard let gateway else { return }
        sessionStatus = "正在理解并补全患者表达…"
        do {
            try ensureRoundIsActive()
            try await gateway.uploadExpression(
                wav: wav,
                primaryTranscript: primaryTranscript
            )
            try ensureRoundIsActive()
            response = try await gateway.command("stop_capture")
        } catch let error as GatewayClientError {
            guard
                isStoppedConflict(error),
                !stoppedSessionRecoveryAttempted,
                sessionStarted,
                !safetyAbortInProgress
            else {
                throw error
            }
            stoppedSessionRecoveryAttempted = true
            let created = try await gateway.createSession(
                language: selectedProfileLanguage,
                profileRef: selectedProfileRef
            )
            activeSessionID = created.session.sessionId
            response = created
            response = try await gateway.command("start_capture")
            try ensureRoundIsActive()
            try await gateway.uploadExpression(
                wav: wav,
                primaryTranscript: primaryTranscript
            )
            try ensureRoundIsActive()
            response = try await gateway.command("stop_capture")
        }
        try ensureRoundIsActive()
        response = try await gateway.command(
            "proceed_without_heard_confirmation"
        )
        try await presentFirstCandidate()
    }

    private func submitVoiceCommand(
        wav: Data,
        primaryTranscript: String
    ) async throws {
        guard let gateway else { return }
        guard !primaryTranscript.isEmpty else {
            try await replayCurrentCandidate(
                status: "没有听清语音回应，正在重新朗读候选。"
            )
            return
        }
        let interpretation = try await gateway.interpretCommand(
            wav: wav,
            primaryTranscript: primaryTranscript,
            promptID: currentPromptID
        )
        try await applyVoiceInterpretation(interpretation)
    }

    private func applyVoiceInterpretation(
        _ interpretation: EarbudInterpretation
    ) async throws {
        guard let gateway, currentCandidate != nil else { return }
        if interpretation.intent == "stop" {
            let sessionIDToStop = activeSessionID
            if let sessionIDToStop {
                response = try await gateway.command(
                    "stop",
                    expectedSessionID: sessionIDToStop
                )
            }
            sessionStarted = false
            activeSessionID = nil
            resetRoundState()
            sessionStatus = "患者已通过语音停止陪伴"
            safetyStatus = "未执行新的外放或记忆写入"
            return
        }

        guard interpretation.consensus else {
            try await replayCurrentCandidate(
                status: "两路识别未达成一致，正在重新朗读候选。"
            )
            return
        }

        switch interpretation.intent {
        case "affirm":
            let evidence = VoiceCommandEvidence(
                interpretationID: interpretation.interpretationId,
                promptID: currentPromptID,
                audioHash: interpretation.audioInputHash
            )
            if (
                additionalVoiceConfirmationRequired
                && firstConfirmationEvidence == nil
            ) {
                firstConfirmationEvidence = evidence
                try await playCurrentCandidateReadback(additional: true)
            } else {
                try await confirmAndPlay(latestEvidence: evidence)
            }
        case "reject", "back":
            audioRouter.stop()
            response = try await gateway.command(
                "reject_current_candidate"
            )
            currentCandidate = nil
            privateReadbackCompleted = false
            firstConfirmationEvidence = nil
            sessionStatus = "患者已否定当前结果，正在准备其他候选…"
            try await presentFirstCandidate()
        case "repeat":
            try await replayCurrentCandidate(
                status: "正在重新朗读当前候选。"
            )
        default:
            try await replayCurrentCandidate(
                status: "没有听清是确认还是否定，正在重新朗读候选。"
            )
        }
    }

    private func presentFirstCandidate() async throws {
        guard let gateway, let response else { return }
        guard let candidate = response.session.candidates.first else {
            throw GatewayClientError.invalidResponse
        }
        currentCandidate = candidate
        privateReadbackCompleted = false
        firstConfirmationEvidence = nil
        self.response = try await gateway.command(
            "prepare_candidate_readback",
            payload: ["candidate_id": candidate.id]
        )
        guard let prepared = self.response else {
            throw GatewayClientError.invalidResponse
        }
        additionalVoiceConfirmationRequired = (
            prepared.strict || candidate.sourceLevel == "L3"
        )
        try await playCurrentCandidateReadback(additional: false)
    }

    private func replayCurrentCandidate(status: String) async throws {
        sessionStatus = status
        try await playCurrentCandidateReadback(
            additional: firstConfirmationEvidence != nil
        )
    }

    private func playCurrentCandidateReadback(
        additional: Bool
    ) async throws {
        guard
            let gateway,
            currentCandidate != nil,
            let sessionID = activeSessionID
        else {
            return
        }
        silenceTask?.cancel()
        privateReadbackCompleted = false
        currentPromptID = UUID().uuidString
        let audio = try await gateway.audio(kind: "neutral")
        sessionStatus = additional
            ? "正在耳机中再次完整朗读候选…"
            : "正在耳机中播放候选结果…"
        try audioRouter.playPrivateAudio(audio) { [weak self] success in
            Task { @MainActor in
                guard let self else { return }
                guard
                    success,
                    self.sessionStarted,
                    self.activeSessionID == sessionID
                else {
                    if !success {
                        self.fail(AudioRouterError.earbudsNotActive)
                    }
                    return
                }
                self.privateReadbackCompleted = true
                let instruction = additional
                    ? "请再次说是或嗯来确认，说不是来更换结果。"
                    : "如果正确，请说是、嗯或没错；如果错误，请说不是或不对。"
                do {
                    try self.audioRouter.playPrivateText(
                        instruction,
                        language: "zh-CN"
                    ) { [weak self] instructionPlayed in
                        Task { @MainActor in
                            guard let self else { return }
                            guard
                                instructionPlayed,
                                self.sessionStarted,
                                self.activeSessionID == sessionID
                            else {
                                if !instructionPlayed {
                                    self.fail(
                                        AudioRouterError.earbudsNotActive
                                    )
                                }
                                return
                            }
                            self.startVoiceCommandCapture(
                                sessionID: sessionID,
                                additional: additional
                            )
                        }
                    }
                } catch {
                    self.fail(error)
                }
            }
        }
    }

    private func startVoiceCommandCapture(
        sessionID: String,
        additional: Bool
    ) {
        guard
            sessionStarted,
            !safetyAbortInProgress,
            activeSessionID == sessionID
        else {
            return
        }
        sessionStatus = additional
            ? "等待患者再次语音确认或否定"
            : "等待患者说“是/嗯”或“不是/不对”"
        safetyStatus = "语音回应需经两路识别一致后才会确认"
        captureBoundaryReached = false
        headset.startCapture(.command, sessionID: sessionID)
    }

    private func confirmAndPlay(
        latestEvidence: VoiceCommandEvidence
    ) async throws {
        guard let gateway, privateReadbackCompleted else { return }
        var interpretationIDs = [latestEvidence.interpretationID]
        if let first = firstConfirmationEvidence {
            interpretationIDs.insert(first.interpretationID, at: 0)
        }
        response = try await gateway.command(
            "confirm_neutral_playback",
            payload: [
                "private_readback_completed": true,
                "voice_interpretation_ids": interpretationIDs,
            ],
            confirmationMethod: "voice_semantic"
        )
        let audio = try await gateway.audio(kind: "neutral")
        let playbackID = UUID().uuidString
        sessionStatus = "已确认，正在通过手机扬声器播放完整句子…"
        safetyStatus = "外放使用系统中性音，不使用患者克隆声音"
        do {
            try audioRouter.playPublicAudio(audio) { [weak self] success in
                Task { @MainActor in
                    guard let self, let gateway = self.gateway else { return }
                    do {
                        self.response = try await gateway.command(
                            success
                                ? "playback_completed"
                                : "playback_failed",
                            payload: [
                                "playback_id": playbackID,
                                "output_channel": "iphone_speaker",
                            ]
                        )
                        if success {
                            self.sessionStatus = "本次表达已播放，继续等待下一次表达"
                            try await self.beginNextExpressionRound()
                        } else {
                            self.sessionStatus = "手机播放失败；本次不会写入确认记忆"
                        }
                    } catch {
                        self.fail(error)
                    }
                }
            }
        } catch {
            _ = try? await gateway.command(
                "playback_failed",
                payload: [
                    "playback_id": playbackID,
                    "output_channel": "iphone_speaker",
                ]
            )
            throw error
        }
    }

    private func restartAfterEmptyCapture(
        _ purpose: CapturePurpose
    ) async {
        guard
            sessionStarted,
            !safetyAbortInProgress,
            let sessionID = activeSessionID
        else {
            return
        }
        switch purpose {
        case .expression:
            stopExpressionTimer(reset: true)
            sessionStatus = "没有收到有效表达，继续等待患者说话。"
            captureBoundaryReached = false
            headset.startCapture(.expression, sessionID: sessionID)
        case .command:
            sessionStatus = "没有收到确认语音，请再说一次。"
            captureBoundaryReached = false
            headset.startCapture(.command, sessionID: sessionID)
        }
    }

    private func ensureRoundIsActive() throws {
        try Task.checkCancellation()
        guard
            sessionStarted,
            !safetyAbortInProgress,
            activeSessionID != nil
        else {
            throw CancellationError()
        }
    }

    private func isStoppedConflict(_ error: GatewayClientError) -> Bool {
        if case let .server(code, message) = error {
            return code == 409
                && message.localizedCaseInsensitiveContains("stopped")
        }
        return false
    }

    private func resetRoundState() {
        response = nil
        currentCandidate = nil
        privateReadbackCompleted = false
        additionalVoiceConfirmationRequired = false
        firstConfirmationEvidence = nil
        currentPromptID = ""
        captureBoundaryReached = false
    }

    private func startExpressionTimerIfNeeded() {
        guard expressionTimerTask == nil else { return }
        expressionElapsedSeconds = 0
        expressionTimerVisible = true
        expressionTimerActive = true
        let startedAt = Date()
        expressionTimerTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 1_000_000_000)
                guard !Task.isCancelled, let self else { return }
                self.expressionElapsedSeconds = max(
                    1,
                    Int(Date().timeIntervalSince(startedAt))
                )
            }
        }
    }

    private func stopExpressionTimer(reset: Bool) {
        expressionTimerTask?.cancel()
        expressionTimerTask = nil
        expressionTimerActive = false
        if reset {
            expressionElapsedSeconds = 0
            expressionTimerVisible = false
        }
    }

    private func fail(_ error: Error) {
        stopExpressionTimer(reset: false)
        errorMessage = error.localizedDescription
        sessionStatus = "发生错误，本次未确认或外放"
        safetyStatus = "仅使用系统中性音"
        if case let GatewayClientError.server(code, message) = error,
           code == 409,
           message.localizedCaseInsensitiveContains("stopped") {
            sessionStarted = false
            activeSessionID = nil
            sessionStatus = "会话已经安全停止，请重新点击“开始陪伴”"
        }
    }

    private func abortForHardwareSafety(_ reason: String) {
        guard sessionStarted, !safetyAbortInProgress else { return }
        let sessionIDToStop = activeSessionID
        safetyAbortInProgress = true
        silenceTask?.cancel()
        stopExpressionTimer(reset: true)
        captureProcessingTask?.cancel()
        activeSessionID = nil
        audioRouter.stop()
        sessionStatus = "\(reason)，正在安全停止陪伴"
        safetyStatus = "未执行新的确认、外放或记忆写入"
        Task {
            if let gateway, let sessionIDToStop {
                _ = try? await gateway.command(
                    "stop",
                    expectedSessionID: sessionIDToStop
                )
            }
            sessionStarted = false
            safetyAbortInProgress = false
            resetRoundState()
            sessionStatus = "\(reason)，陪伴已安全停止，可以重新开始"
        }
    }
}

private struct VoiceCommandEvidence {
    let interpretationID: String
    let promptID: String
    let audioHash: String
}
