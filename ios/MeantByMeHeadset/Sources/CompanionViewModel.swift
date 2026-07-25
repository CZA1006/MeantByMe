import Combine
import Foundation

private enum CompanionFlowError: LocalizedError {
    case missingQAResponse
    case missingQAAudio
    case noExpressionCandidates

    var errorDescription: String? {
        switch self {
        case .missingQAResponse:
            return "AI 暂时没有生成可用回答，请重新说一次"
        case .missingQAAudio:
            return "AI 已生成文字回答，但耳机语音生成失败，请重新说一次"
        case .noExpressionCandidates:
            return "AI 暂时没有生成可用的表达候选，请重新说一次"
        }
    }
}

@MainActor
final class CompanionViewModel: ObservableObject {
    @Published var mode: CompanionMode = .expression
    @Published private(set) var sessionStarted = false
    @Published private(set) var sessionStatus = "等待陪伴开始"
    @Published private(set) var expressionElapsedSeconds = 0
    @Published private(set) var expressionTimerActive = false
    @Published private(set) var expressionTimerVisible = false
    @Published private(set) var expressionCancellationInProgress = false
    @Published var speakerVolumeTestPresented = false
    @Published var userSettingsPresented = false
    @Published private(set) var profiles: [UserProfileSummary] = []
    @Published private(set) var selectedProfileRef: String
    @Published private(set) var selectedProfileLabel: String
    @Published private(set) var selectedProfileLanguage: String
    @Published private(set) var selectedProfileDetail: UserProfileDetail?
    @Published private(set) var profilesLoading = false
    @Published private(set) var profileDetailLoading = false
    @Published private(set) var profileDetailError: String?
    @Published var errorMessage: String?

    let headset = ViaimHeadsetService()
    private let audioRouter = AudioRouter()
    private var gateway: GatewayClient?
    private var response: DemoResponse?
    private var qaResponse: QASessionResponse?
    private var silenceTask: Task<Void, Never>?
    private var expressionTimerTask: Task<Void, Never>?
    private var captureProcessingTask: Task<Void, Never>?
    private var safetyAbortInProgress = false
    private var captureBoundaryReached = false
    private var activeCapturePurpose: CapturePurpose?
    private var activeSessionID: String?
    private var activeQATurnID: String?
    private var stoppedSessionRecoveryAttempted = false
    private var currentCandidate: Candidate?
    private var privateReadbackCompleted = false
    private var additionalVoiceConfirmationRequired = false
    private var firstConfirmationEvidence: VoiceCommandEvidence?
    private var currentPromptID = ""
    private var cancellables: Set<AnyCancellable> = []
    private var profileDetailCache: [String: UserProfileDetail] = [:]
    private var profileDetailLoadingRefs: Set<String> = []

    var headsetConnected: Bool { headset.connected }
    var headsetStatus: String { headset.status }
    var canEditCurrentUser: Bool { !sessionStarted }
    var canCancelCurrentExpression: Bool {
        sessionStarted
            && activeSessionID != nil
            && !safetyAbortInProgress
            && !expressionCancellationInProgress
    }
    var canFinishSpeaking: Bool {
        guard
            sessionStarted,
            headset.recording,
            !captureBoundaryReached,
            !safetyAbortInProgress,
            !expressionCancellationInProgress
        else {
            return false
        }
        return activeCapturePurpose == .expression
            || activeCapturePurpose == .question
    }
    var currentRoundLabel: String {
        mode == .qa ? "本次提问" : "本次表达"
    }
    var cancelActionLabel: String {
        if expressionCancellationInProgress {
            return "正在丢弃这句话…"
        }
        return "丢弃这句话"
    }
    var activeGuidance: String {
        if mode == .qa {
            return "持续陪伴中。停顿 5 秒后，AI 会补全问题并直接在耳机中回答。"
        }
        return "持续陪伴中。停顿 5 秒后自动补全；说“是/嗯”确认，说“不是/不对”更换。"
    }
    var cancelGuidance: String {
        mode == .qa
            ? "只放弃当前问题及其临时上下文，随后会自动继续聆听。"
            : "只放弃当前这句话，随后会自动继续聆听。"
    }

    init() {
        let defaults = UserDefaults.standard
        selectedProfileRef = defaults.string(
            forKey: "selected_profile_ref"
        ) ?? "lin_yue_demo"
        selectedProfileLabel = defaults.string(
            forKey: "selected_profile_label"
        ) ?? "林悦"
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
            self.activeCapturePurpose = nil
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
        if !profiles.isEmpty {
            await loadSelectedProfileDetail()
            return
        }
        profilesLoading = true
        defer { profilesLoading = false }
        do {
            let loaded = visibleProfiles(try await gateway.listProfiles())
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
            prefetchBuiltInProfileDetails()
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

    func loadSelectedProfileDetail(forceReload: Bool = false) async {
        guard let gateway else { return }
        let profileRef = selectedProfileRef
        if !forceReload, let cached = profileDetailCache[profileRef] {
            selectedProfileDetail = cached
            profileDetailError = nil
            profileDetailLoading = false
            return
        }
        if profileDetailLoadingRefs.contains(profileRef) {
            profileDetailLoading = true
            return
        }
        profileDetailLoadingRefs.insert(profileRef)
        selectedProfileDetail = nil
        profileDetailError = nil
        profileDetailLoading = true
        defer {
            profileDetailLoadingRefs.remove(profileRef)
            if selectedProfileRef == profileRef {
                profileDetailLoading = false
            }
        }
        do {
            let detail = try await gateway.profileDetail(
                profileRef: profileRef
            )
            profileDetailCache[profileRef] = detail
            guard selectedProfileRef == profileRef else { return }
            selectedProfileDetail = detail
        } catch {
            guard selectedProfileRef == profileRef else { return }
            profileDetailError = error.localizedDescription
        }
    }

    func createUserProfile(
        _ input: NewUserProfileInput
    ) async -> Bool {
        guard let gateway, !sessionStarted else { return false }
        do {
            let created = try await gateway.createProfile(input)
            profiles = visibleProfiles(try await gateway.listProfiles())
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
            profiles = visibleProfiles(try await gateway.listProfiles())
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
        selectedProfileLabel = profile.displayLabel
        selectedProfileLanguage = profile.defaultLanguage
        selectedProfileDetail = profileDetailCache[profile.profileRef]
        profileDetailError = nil
        profileDetailLoading = profileDetailLoadingRefs.contains(
            profile.profileRef
        )
        let defaults = UserDefaults.standard
        defaults.set(profile.profileRef, forKey: "selected_profile_ref")
        defaults.set(profile.displayLabel, forKey: "selected_profile_label")
        defaults.set(
            profile.defaultLanguage,
            forKey: "selected_profile_language"
        )
    }

    private func visibleProfiles(
        _ loaded: [UserProfileSummary]
    ) -> [UserProfileSummary] {
        loaded.filter { $0.profileRef != "no_profile" }
    }

    private func prefetchBuiltInProfileDetails() {
        guard let gateway else { return }
        let profileRefs = profiles
            .map(\.profileRef)
            .filter {
                ["lin_yue_demo", "david_demo"].contains($0)
                    && profileDetailCache[$0] == nil
                    && $0 != selectedProfileRef
            }
        guard !profileRefs.isEmpty else { return }
        Task { [weak self] in
            guard let self else { return }
            for profileRef in profileRefs {
                guard
                    self.profileDetailCache[profileRef] == nil,
                    !self.profileDetailLoadingRefs.contains(profileRef)
                else {
                    continue
                }
                self.profileDetailLoadingRefs.insert(profileRef)
                do {
                    let detail = try await gateway.profileDetail(
                        profileRef: profileRef
                    )
                    self.profileDetailCache[profileRef] = detail
                    if self.selectedProfileRef == profileRef {
                        self.selectedProfileDetail = detail
                        self.profileDetailError = nil
                    }
                } catch {
                    if self.selectedProfileRef == profileRef {
                        self.profileDetailError = error.localizedDescription
                    }
                }
                self.profileDetailLoadingRefs.remove(profileRef)
                if self.selectedProfileRef == profileRef {
                    self.profileDetailLoading = false
                }
            }
        }
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
        endSpeakerVolumeTest()
        sessionStarted = true
        do {
            if mode == .qa {
                try await beginQAConversation()
            } else {
                try await beginNextExpressionRound()
            }
        } catch {
            fail(error)
        }
    }

    func finishSpeaking() {
        guard canFinishSpeaking else { return }
        silenceTask?.cancel()
        captureBoundaryReached = true
        stopExpressionTimer(reset: false)
        sessionStatus = mode == .qa
            ? "你已说完，正在理解并回答…"
            : "你已说完，正在理解并补全表达…"
        headset.stopCapture()
    }

    func stopCompanion() async {
        guard !safetyAbortInProgress else { return }
        safetyAbortInProgress = true
        let sessionIDToStop = activeSessionID
        silenceTask?.cancel()
        stopExpressionTimer(reset: true)
        captureProcessingTask?.cancel()
        activeCapturePurpose = nil
        activeSessionID = nil
        sessionStatus = "正在结束陪伴并丢弃未完成的表达…"
        audioRouter.stop()
        await withCheckedContinuation { continuation in
            headset.discardCurrentCapture {
                continuation.resume()
            }
        }
        if let gateway, let sessionIDToStop {
            if mode == .qa {
                _ = try? await gateway.stopQASession(
                    expectedSessionID: sessionIDToStop
                )
            } else {
                _ = try? await gateway.command(
                    "stop",
                    expectedSessionID: sessionIDToStop
                )
            }
        }
        sessionStarted = false
        safetyAbortInProgress = false
        resetRoundState()
        sessionStatus = "陪伴已结束"
    }

    func cancelCurrentExpression() async {
        if mode == .qa {
            await cancelCurrentQuestion()
            return
        }
        guard
            let gateway,
            let sessionIDToCancel = activeSessionID,
            canCancelCurrentExpression
        else {
            return
        }

        expressionCancellationInProgress = true
        silenceTask?.cancel()
        stopExpressionTimer(reset: true)
        captureProcessingTask?.cancel()
        captureProcessingTask = nil
        activeCapturePurpose = nil
        activeSessionID = nil
        audioRouter.stop()
        resetRoundState()
        sessionStatus = "正在丢弃本次表达…"

        await withCheckedContinuation { continuation in
            headset.discardCurrentCapture {
                continuation.resume()
            }
        }

        guard sessionStarted, !safetyAbortInProgress else {
            expressionCancellationInProgress = false
            return
        }

        do {
            var cancellationAccepted = true
            do {
                _ = try await gateway.command(
                    "cancel_expression",
                    expectedSessionID: sessionIDToCancel
                )
            } catch let error as GatewayClientError
                where isFinishedExpressionConflict(error) {
                // Playback may have completed at the same instant the button
                // was pressed. There is then nothing left to cancel, but the
                // companion should still advance to a fresh round.
                cancellationAccepted = false
            }
            guard sessionStarted, !safetyAbortInProgress else {
                expressionCancellationInProgress = false
                return
            }
            try await beginNextExpressionRound()
            sessionStatus = cancellationAccepted
                ? "已结束上一条表达，正在等待患者重新说"
                : "上一轮已经结束，正在等待患者重新说"
        } catch {
            expressionCancellationInProgress = false
            guard sessionStarted, !safetyAbortInProgress else { return }
            fail(error)
            return
        }
        expressionCancellationInProgress = false
    }

    private func cancelCurrentQuestion() async {
        guard
            let gateway,
            let sessionID = activeSessionID,
            canCancelCurrentExpression
        else {
            return
        }
        let turnID = activeQATurnID
        expressionCancellationInProgress = true
        silenceTask?.cancel()
        stopExpressionTimer(reset: true)
        captureProcessingTask?.cancel()
        captureProcessingTask = nil
        activeCapturePurpose = nil
        audioRouter.stop()
        activeQATurnID = nil
        captureBoundaryReached = false
        sessionStatus = "正在丢弃本次提问…"

        await withCheckedContinuation { continuation in
            headset.discardCurrentCapture {
                continuation.resume()
            }
        }
        if let turnID {
            _ = try? await gateway.cancelQATurn(
                turnID: turnID,
                expectedSessionID: sessionID
            )
        }
        guard
            sessionStarted,
            !safetyAbortInProgress,
            activeSessionID == sessionID
        else {
            expressionCancellationInProgress = false
            return
        }
        beginNextQuestionCapture()
        sessionStatus = "已结束上一轮提问，正在等待患者重新提问"
        expressionCancellationInProgress = false
    }

    private func beginQAConversation() async throws {
        guard let gateway, sessionStarted, !safetyAbortInProgress else {
            return
        }
        silenceTask?.cancel()
        stopExpressionTimer(reset: true)
        captureProcessingTask?.cancel()
        resetRoundState()
        activeQATurnID = nil
        activeSessionID = nil
        let created = try await gateway.createQASession(
            language: selectedProfileLanguage,
            profileRef: selectedProfileRef
        )
        qaResponse = created
        activeSessionID = created.sessionId
        beginNextQuestionCapture()
    }

    private func beginNextQuestionCapture() {
        guard
            sessionStarted,
            !safetyAbortInProgress,
            let sessionID = activeSessionID
        else {
            return
        }
        silenceTask?.cancel()
        stopExpressionTimer(reset: true)
        captureBoundaryReached = false
        activeQATurnID = UUID().uuidString
        sessionStatus = "正在持续聆听；停顿 5 秒后 AI 将直接回答"
        startHeadsetCapture(.question, sessionID: sessionID)
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
        sessionStatus = "正在持续聆听；停顿 5 秒后自动理解本次表达"
        captureBoundaryReached = false
        startHeadsetCapture(
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
            delay = 5_000_000_000
            sessionStatus = "检测到患者说话；继续说话会重新计算 5 秒"
        case .question:
            startExpressionTimerIfNeeded()
            delay = 5_000_000_000
            sessionStatus = "检测到患者提问；继续说话会重新计算 5 秒"
        case .command:
            delay = 1_200_000_000
            sessionStatus = "正在聆听患者的确认或否定…"
        }
        silenceTask = Task {
            try? await Task.sleep(nanoseconds: delay)
            guard !Task.isCancelled else { return }
            captureBoundaryReached = true
            if purpose == .expression || purpose == .question {
                stopExpressionTimer(reset: false)
            }
            switch purpose {
            case .expression:
                sessionStatus = "已静默 5 秒，正在结束本次表达…"
            case .question:
                sessionStatus = "已静默 5 秒，正在理解并回答问题…"
            case .command:
                sessionStatus = "正在理解患者的语音回应…"
            }
            headset.stopCapture()
        }
    }

    private func handleCapture(_ capture: EarbudCapture) async {
        guard !Task.isCancelled else { return }
        guard sessionStarted, !safetyAbortInProgress else { return }
        guard capture.sessionID == activeSessionID else { return }
        if capture.purpose == .expression || capture.purpose == .question {
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
            case .question:
                try await submitQuestionCapture(
                    wav: wav,
                    primaryTranscript: capture.primaryTranscript,
                    sessionID: capture.sessionID
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

    private func submitQuestionCapture(
        wav: Data,
        primaryTranscript: String,
        sessionID: String
    ) async throws {
        guard
            let gateway,
            let turnID = activeQATurnID,
            activeSessionID == sessionID
        else {
            return
        }
        sessionStatus = "正在补全问题并生成回答…"
        let result = try await gateway.askAI(
            wav: wav,
            primaryTranscript: primaryTranscript,
            turnID: turnID,
            expectedSessionID: sessionID
        )
        try Task.checkCancellation()
        guard
            sessionStarted,
            !safetyAbortInProgress,
            activeSessionID == sessionID,
            activeQATurnID == turnID
        else {
            return
        }
        qaResponse = result
        guard let answer = result.response else {
            throw CompanionFlowError.missingQAResponse
        }
        guard result.audioAvailable else {
            throw CompanionFlowError.missingQAAudio
        }
        let audio = try await gateway.qaAudio(
            turnID: turnID,
            expectedSessionID: sessionID
        )
        sessionStatus = answer.shouldClarify
            ? "问题含义不够明确，AI 正在耳机中追问…"
            : "AI 正在耳机中回答…"
        try audioRouter.playPrivateAudio(audio) { [weak self] success in
            Task { @MainActor in
                guard let self else { return }
                guard
                    success,
                    self.sessionStarted,
                    self.activeSessionID == sessionID,
                    self.activeQATurnID == turnID
                else {
                    if !success {
                        self.fail(AudioRouterError.earbudsNotActive)
                    }
                    return
                }
                self.activeQATurnID = nil
                self.beginNextQuestionCapture()
            }
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
#if DEBUG
            print(
                "[MeantByMeFlow] no_candidates "
                    + "stage=\(response.session.stage) "
                    + "failure_status=\(response.failureStatus ?? "<none>")"
            )
#endif
            throw CompanionFlowError.noExpressionCandidates
        }
        currentCandidate = candidate
        privateReadbackCompleted = false
        firstConfirmationEvidence = nil
        let prepared = try await gateway.command(
            "prepare_candidate_readback",
            payload: ["candidate_id": candidate.id]
        )
        self.response = prepared
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
            let candidate = currentCandidate,
            let sessionID = activeSessionID
        else {
            return
        }
        silenceTask?.cancel()
        privateReadbackCompleted = false
        currentPromptID = UUID().uuidString
        sessionStatus = additional
            ? "正在耳机中再次完整朗读候选…"
            : "正在耳机中播放候选结果…"
        let completion: (Bool) -> Void = { [weak self] success in
            Task { @MainActor in
                self?.completePrivateCandidateReadback(
                    success: success,
                    additional: additional,
                    sessionID: sessionID
                )
            }
        }
        if selectedProfileRef == "lin_yue_demo" {
            try audioRouter.playPrivateText(
                candidate.text,
                language: candidate.language,
                completion: completion
            )
        } else {
            let audio = try await gateway.audio(kind: "neutral")
            try audioRouter.playPrivateAudio(
                audio,
                completion: completion
            )
        }
    }

    private func completePrivateCandidateReadback(
        success: Bool,
        additional: Bool,
        sessionID: String
    ) {
        guard
            success,
            sessionStarted,
            activeSessionID == sessionID
        else {
            if !success {
                fail(AudioRouterError.earbudsNotActive)
            }
            return
        }
        privateReadbackCompleted = true
        let instruction = additional
            ? "请再次说是或嗯来确认，说不是来更换结果。"
            : "如果正确，请说是、嗯或没错；如果错误，请说不是或不对。"
        do {
            try audioRouter.playPrivateText(
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
                        sessionID: sessionID
                    )
                }
            }
        } catch {
            fail(error)
        }
    }

    private func startVoiceCommandCapture(
        sessionID: String
    ) {
        guard
            sessionStarted,
            !safetyAbortInProgress,
            activeSessionID == sessionID
        else {
            return
        }
        sessionStatus = "等待用户回复"
        captureBoundaryReached = false
        startHeadsetCapture(.command, sessionID: sessionID)
    }

    private func confirmAndPlay(
        latestEvidence: VoiceCommandEvidence
    ) async throws {
        guard
            let gateway,
            let candidate = currentCandidate,
            privateReadbackCompleted
        else {
            return
        }
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
        let playbackID = UUID().uuidString
        sessionStatus = "已确认，正在通过手机扬声器播放完整句子…"
        let completion: (Bool) -> Void = { [weak self] success in
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
        do {
            if selectedProfileRef == "lin_yue_demo" {
                try audioRouter.playPublicText(
                    candidate.text,
                    language: candidate.language,
                    completion: completion
                )
            } else {
                let audio = try await gateway.audio(kind: "neutral")
                try audioRouter.playPublicAudio(
                    audio,
                    completion: completion
                )
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
            startHeadsetCapture(.expression, sessionID: sessionID)
        case .question:
            stopExpressionTimer(reset: true)
            sessionStatus = "没有收到有效问题，继续等待患者提问。"
            captureBoundaryReached = false
            startHeadsetCapture(.question, sessionID: sessionID)
        case .command:
            sessionStatus = "没有收到确认语音，请再说一次。"
            captureBoundaryReached = false
            startHeadsetCapture(.command, sessionID: sessionID)
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

    private func isFinishedExpressionConflict(
        _ error: GatewayClientError
    ) -> Bool {
        if case let .server(code, message) = error {
            return code == 409
                && message.localizedCaseInsensitiveContains(
                    "unspoken active expression"
                )
        }
        return false
    }

    private func resetRoundState() {
        response = nil
        qaResponse = nil
        activeQATurnID = nil
        currentCandidate = nil
        privateReadbackCompleted = false
        additionalVoiceConfirmationRequired = false
        firstConfirmationEvidence = nil
        currentPromptID = ""
        captureBoundaryReached = false
        activeCapturePurpose = nil
    }

    private func startHeadsetCapture(
        _ purpose: CapturePurpose,
        sessionID: String
    ) {
        activeCapturePurpose = purpose
        headset.startCapture(purpose, sessionID: sessionID)
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
#if DEBUG
        print(
            "[MeantByMeFlow] failed "
                + "type=\(String(reflecting: type(of: error))) "
                + "message=\(error.localizedDescription)"
        )
#endif
        errorMessage = error.localizedDescription
        sessionStatus = "发生错误，本次未确认或外放"
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
        activeCapturePurpose = nil
        audioRouter.stop()
        headset.discardCurrentCapture {}
        sessionStatus = "\(reason)，正在安全停止陪伴"
        Task {
            if let gateway, let sessionIDToStop {
                if self.mode == .qa {
                    _ = try? await gateway.stopQASession(
                        expectedSessionID: sessionIDToStop
                    )
                } else {
                    _ = try? await gateway.command(
                        "stop",
                        expectedSessionID: sessionIDToStop
                    )
                }
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
