import Foundation

enum CompanionMode: String {
    case expression
    case qa
}

struct UserProfileSummary: Decodable, Identifiable, Hashable {
    let profileRef: String
    let label: String
    let defaultLanguage: String
    let languages: [String]
    let source: String
    let simulated: Bool?
    let memoryCount: Int?

    var id: String { profileRef }

    enum CodingKeys: String, CodingKey {
        case label, languages, source, simulated
        case profileRef = "profile_ref"
        case defaultLanguage = "default_language"
        case memoryCount = "memory_count"
    }
}

struct UserProfileMemory: Decodable, Identifiable {
    let id: String
    let text: String
    let kind: String
    let verificationLevel: String
    let source: String
    let sensitivity: String
    let promptEligible: Bool

    enum CodingKeys: String, CodingKey {
        case id, text, kind, source, sensitivity
        case verificationLevel = "verification_level"
        case promptEligible = "prompt_eligible"
    }
}

struct UserProfileDetail: Decodable {
    let profileRef: String
    let profileId: String
    let label: String
    let displayName: String
    let defaultLanguage: String
    let languages: [String]
    let source: String
    let simulated: Bool
    let memoryCount: Int
    let memories: [UserProfileMemory]

    enum CodingKeys: String, CodingKey {
        case label, languages, source, simulated, memories
        case profileRef = "profile_ref"
        case profileId = "profile_id"
        case displayName = "display_name"
        case defaultLanguage = "default_language"
        case memoryCount = "memory_count"
    }
}

struct ProfilesResponse: Decodable {
    let profiles: [UserProfileSummary]
}

struct ProfileSummaryResponse: Decodable {
    let profile: UserProfileSummary
}

struct ProfileDetailResponse: Decodable {
    let profile: UserProfileDetail
}

struct NewUserProfileInput: Encodable {
    let displayName: String
    let language: String
    let background: String
    let relationships: String
    let routines: String
    let interests: String
    let communicationPreferences: String
    let additionalNotes: String

    enum CodingKeys: String, CodingKey {
        case language, background, relationships, routines, interests
        case displayName = "display_name"
        case communicationPreferences = "communication_preferences"
        case additionalNotes = "additional_notes"
    }
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
    let interpretationId: String
    let intent: String
    let consensus: Bool
    let stage: String
    let promptId: String
    let audioInputHash: String

    enum CodingKeys: String, CodingKey {
        case intent, consensus, stage
        case interpretationId = "interpretation_id"
        case promptId = "prompt_id"
        case audioInputHash = "audio_input_hash"
    }
}

struct QAResult: Decodable {
    let understoodQuestion: String
    let patientSupportedSpans: [String]
    let aiAddedSpans: [String]
    let uncertainty: String
    let shouldClarify: Bool
    let clarificationQuestion: String?
    let answer: String?
    let riskLevel: String
    let status: String
    let error: String?

    enum CodingKeys: String, CodingKey {
        case uncertainty, answer, status, error
        case understoodQuestion = "understood_question"
        case patientSupportedSpans = "patient_supported_spans"
        case aiAddedSpans = "ai_added_spans"
        case shouldClarify = "should_clarify"
        case clarificationQuestion = "clarification_question"
        case riskLevel = "risk_level"
    }
}

struct QASessionResponse: Decodable {
    let sessionId: String
    let sessionToken: String?
    let stopped: Bool
    let turnCount: Int
    let latestTurnId: String?
    let response: QAResult?
    let audioAvailable: Bool
    let voiceMode: String
    let memoryWriteEnabled: Bool

    enum CodingKeys: String, CodingKey {
        case stopped, response
        case sessionId = "session_id"
        case sessionToken = "session_token"
        case turnCount = "turn_count"
        case latestTurnId = "latest_turn_id"
        case audioAvailable = "audio_available"
        case voiceMode = "voice_mode"
        case memoryWriteEnabled = "memory_write_enabled"
    }
}
