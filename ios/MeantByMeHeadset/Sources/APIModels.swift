import Foundation

enum CompanionMode: String {
    case expression
    case qa
}

struct Candidate: Decodable, Identifiable {
    let id: String
    let text: String
    let language: String
    let riskLevel: String
    let sourceLevel: String

    enum CodingKeys: String, CodingKey {
        case id, text, language
        case riskLevel = "risk_level"
        case sourceLevel = "source_level"
    }
}

struct RuntimeView: Decodable {
    let sessionId: String
    let stage: String
    let heardStable: [String]
    let heardUncertain: [String]
    let clarificationQuestion: String?
    let clarificationOptions: [String]
    let candidates: [Candidate]

    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
        case stage
        case heardStable = "heard_stable"
        case heardUncertain = "heard_uncertain"
        case clarificationQuestion = "clarification_question"
        case clarificationOptions = "clarification_options"
        case candidates
    }
}

struct DemoAudioState: Decodable {
    let neutralAvailable: Bool
    let personalAvailable: Bool

    enum CodingKeys: String, CodingKey {
        case neutralAvailable = "neutral_available"
        case personalAvailable = "personal_available"
    }
}

struct DemoResponse: Decodable {
    let mode: String
    let session: RuntimeView
    let sessionToken: String?
    let selectedCandidateId: String?
    let selectedCandidate: Candidate?
    let strict: Bool
    let riskLevel: String
    let failureStatus: String?
    let audio: DemoAudioState

    enum CodingKeys: String, CodingKey {
        case mode, session, strict, audio
        case sessionToken = "session_token"
        case selectedCandidateId = "selected_candidate_id"
        case selectedCandidate = "selected_candidate"
        case riskLevel = "risk_level"
        case failureStatus = "failure_status"
    }
}

struct EarbudInterpretation: Decodable {
    let intent: String
    let consensus: Bool
    let stage: String
    let audioInputHash: String

    enum CodingKeys: String, CodingKey {
        case intent, consensus, stage
        case audioInputHash = "audio_input_hash"
    }
}
