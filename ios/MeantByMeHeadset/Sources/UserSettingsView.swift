import SwiftUI
import UniformTypeIdentifiers

struct UserSettingsView: View {
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var companion: CompanionViewModel
    @State private var addUserPresented = false

    var body: some View {
        NavigationView {
            Form {
                Section(
                    header: Text("当前用户"),
                    footer: Text(
                        "开始陪伴后将锁定当前用户，避免不同用户的档案发生混用。"
                    )
                ) {
                    if companion.profilesLoading && companion.profiles.isEmpty {
                        HStack {
                            ProgressView()
                            Text("正在读取服务器用户…")
                        }
                    } else {
                        Picker(
                            "选择用户",
                            selection: Binding(
                                get: {
                                    companion.selectedProfileRef
                                },
                                set: { profileRef in
                                    Task {
                                        await companion.selectProfile(
                                            profileRef
                                        )
                                    }
                                }
                            )
                        ) {
                            ForEach(companion.profiles) { profile in
                                Text(profile.label)
                                    .tag(profile.profileRef)
                            }
                        }
                        .disabled(!companion.canEditCurrentUser)

                        NavigationLink {
                            UserProfileDetailView()
                                .environmentObject(companion)
                        } label: {
                            Label(
                                "查看人物档案",
                                systemImage: "person.text.rectangle"
                            )
                        }
                    }
                }

                Section {
                    Button {
                        addUserPresented = true
                    } label: {
                        Label("添加新用户", systemImage: "person.badge.plus")
                    }
                    .disabled(!companion.canEditCurrentUser)
                } footer: {
                    Text(
                        "可通过引导问题新建档案，也可导入包含 meantbyme-profile 数据块的 Markdown 文件。"
                    )
                }

                Section("隐私与来源") {
                    Text(
                        "陪护者手工填写的内容只作为 Silver 辅助背景，不能代表患者已经确认的真实意愿，也不会绕过每次表达确认。"
                    )
                    .font(.footnote)
                    .foregroundColor(.secondary)
                }
            }
            .navigationTitle("用户设置")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("完成") { dismiss() }
                }
            }
            .task {
                await companion.refreshProfiles()
            }
            .sheet(isPresented: $addUserPresented) {
                AddUserProfileView()
                    .environmentObject(companion)
            }
        }
    }
}

private struct UserProfileDetailView: View {
    @EnvironmentObject private var companion: CompanionViewModel

    var body: some View {
        Group {
            if let profile = companion.selectedProfileDetail {
                List {
                    Section("用户") {
                        LabeledContentCompat(
                            label: "姓名",
                            value: profile.displayName
                        )
                        LabeledContentCompat(
                            label: "语言",
                            value: profile.languages.joined(separator: "、")
                        )
                        LabeledContentCompat(
                            label: "档案来源",
                            value: sourceLabel(profile.source)
                        )
                        if profile.simulated {
                            Label("模拟演示档案", systemImage: "testtube.2")
                                .foregroundColor(.orange)
                        }
                    }

                    Section("人物档案") {
                        if profile.memories.isEmpty {
                            Text("该用户暂时没有人物档案内容。")
                                .foregroundColor(.secondary)
                        } else {
                            ForEach(profile.memories) { memory in
                                VStack(alignment: .leading, spacing: 7) {
                                    HStack {
                                        Text(kindLabel(memory.kind))
                                            .font(.headline)
                                        Spacer()
                                        Text(
                                            memory.verificationLevel == "gold"
                                                ? "本人已确认"
                                                : "陪护者提供"
                                        )
                                        .font(.caption)
                                        .foregroundColor(
                                            memory.verificationLevel == "gold"
                                                ? .green
                                                : .orange
                                        )
                                    }
                                    Text(memory.text)
                                        .font(.body)
                                    if memory.sensitivity != "ordinary" {
                                        Label(
                                            "敏感信息",
                                            systemImage: "lock.fill"
                                        )
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                    }
                                }
                                .padding(.vertical, 4)
                            }
                        }
                    }
                }
            } else {
                ProgressView("正在读取人物档案…")
            }
        }
        .navigationTitle(companion.selectedProfileLabel)
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await companion.loadSelectedProfileDetail()
        }
    }

    private func sourceLabel(_ source: String) -> String {
        switch source {
        case "questionnaire": return "App 引导填写"
        case "uploaded": return "Markdown 导入"
        case "built_in": return "内置演示"
        default: return source
        }
    }

    private func kindLabel(_ kind: String) -> String {
        switch kind {
        case "personal_background": return "身份与背景"
        case "relationships", "relationship": return "家人与重要关系"
        case "routine": return "日常习惯与安排"
        case "interests", "interest": return "兴趣爱好"
        case "communication_preference": return "沟通偏好"
        case "work": return "工作"
        case "healthcare", "health_and_work": return "健康与照护"
        default: return "其他信息"
        }
    }
}

private struct LabeledContentCompat: View {
    let label: String
    let value: String

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label)
            Spacer()
            Text(value)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.trailing)
        }
    }
}

private enum AddProfileMethod: String, CaseIterable {
    case questions
    case markdown
}

private struct AddUserProfileView: View {
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var companion: CompanionViewModel

    @State private var method: AddProfileMethod = .questions
    @State private var displayName = ""
    @State private var background = ""
    @State private var relationships = ""
    @State private var routines = ""
    @State private var interests = ""
    @State private var communicationPreferences = ""
    @State private var additionalNotes = ""
    @State private var fileImporterPresented = false
    @State private var saving = false

    private var hasProfileAnswer: Bool {
        [
            background,
            relationships,
            routines,
            interests,
            communicationPreferences,
            additionalNotes,
        ].contains { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
    }

    var body: some View {
        NavigationView {
            Form {
                Picker("添加方式", selection: $method) {
                    Text("回答问题").tag(AddProfileMethod.questions)
                    Text("导入 Markdown").tag(AddProfileMethod.markdown)
                }
                .pickerStyle(.segmented)

                if method == .questions {
                    questionnaireSections
                } else {
                    markdownSection
                }
            }
            .navigationTitle("添加新用户")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("取消") { dismiss() }
                        .disabled(saving)
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(saving ? "保存中…" : "保存") {
                        saveQuestionnaire()
                    }
                    .opacity(method == .questions ? 1 : 0)
                    .disabled(
                        method != .questions
                            || saving
                            || displayName.trimmingCharacters(
                                in: .whitespacesAndNewlines
                            ).isEmpty
                            || !hasProfileAnswer
                    )
                }
            }
            .interactiveDismissDisabled(saving)
            .fileImporter(
                isPresented: $fileImporterPresented,
                allowedContentTypes: [.plainText],
                allowsMultipleSelection: false,
                onCompletion: importMarkdown
            )
        }
    }

    @ViewBuilder
    private var questionnaireSections: some View {
        Section("基本信息") {
            TextField("用户姓名（必填）", text: $displayName)
            Text("以下问题至少填写一项。不确定的内容可以留空。")
                .font(.footnote)
                .foregroundColor(.secondary)
        }
        profileQuestion(
            title: "身份与背景",
            prompt: "例如年龄、居住地、职业、重要经历",
            text: $background
        )
        profileQuestion(
            title: "家人与重要关系",
            prompt: "例如家人姓名、关系，以及希望他们如何提供帮助",
            text: $relationships
        )
        profileQuestion(
            title: "日常习惯与安排",
            prompt: "例如作息、固定活动、常去地点",
            text: $routines
        )
        profileQuestion(
            title: "兴趣爱好",
            prompt: "例如喜欢的活动、食物、音乐或话题",
            text: $interests
        )
        profileQuestion(
            title: "沟通偏好与需要的帮助",
            prompt: "例如希望别人放慢语速、一次只问一个问题",
            text: $communicationPreferences
        )
        profileQuestion(
            title: "其他补充",
            prompt: "其他有助于理解用户表达的信息",
            text: $additionalNotes
        )
        Section {
            Text(
                "这些答案由陪护者录入，因此只作为辅助背景，不会被当作患者本人已经确认的表达。"
            )
            .font(.footnote)
            .foregroundColor(.secondary)
        }
    }

    private var markdownSection: some View {
        Section {
            VStack(alignment: .leading, spacing: 14) {
                Label(
                    "导入 Markdown 人物档案",
                    systemImage: "doc.badge.plus"
                )
                .font(.headline)
                Text(
                    "文件必须是 UTF-8 Markdown，并包含一个 meantbyme-profile JSON 数据块。导入成功后会自动选中新用户。"
                )
                .font(.footnote)
                .foregroundColor(.secondary)
                Button {
                    fileImporterPresented = true
                } label: {
                    Label("选择 Markdown 文件", systemImage: "folder")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .disabled(saving)
                if saving {
                    ProgressView("正在导入并验证…")
                }
            }
            .padding(.vertical, 8)
        }
    }

    private func profileQuestion(
        title: String,
        prompt: String,
        text: Binding<String>
    ) -> some View {
        Section(header: Text(title), footer: Text(prompt)) {
            TextEditor(text: text)
                .frame(minHeight: 72)
        }
    }

    private func saveQuestionnaire() {
        saving = true
        let input = NewUserProfileInput(
            displayName: displayName.trimmingCharacters(
                in: .whitespacesAndNewlines
            ),
            language: "zh",
            background: background,
            relationships: relationships,
            routines: routines,
            interests: interests,
            communicationPreferences: communicationPreferences,
            additionalNotes: additionalNotes
        )
        Task {
            let success = await companion.createUserProfile(input)
            saving = false
            if success { dismiss() }
        }
    }

    private func importMarkdown(
        _ result: Result<[URL], Error>
    ) {
        do {
            guard let url = try result.get().first else { return }
            let accessed = url.startAccessingSecurityScopedResource()
            defer {
                if accessed { url.stopAccessingSecurityScopedResource() }
            }
            let data = try Data(contentsOf: url)
            guard data.count <= 64 * 1024 else {
                companion.errorMessage = "人物档案不能超过 64 KiB"
                return
            }
            saving = true
            Task {
                let success = await companion.importUserProfileMarkdown(data)
                saving = false
                if success { dismiss() }
            }
        } catch {
            companion.errorMessage = "无法读取 Markdown 文件：\(error.localizedDescription)"
        }
    }
}
