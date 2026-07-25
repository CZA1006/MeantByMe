import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var companion: CompanionViewModel

    var body: some View {
        NavigationView {
            VStack(spacing: 24) {
                VStack(spacing: 8) {
                    Image(systemName: "earbuds")
                        .font(.system(size: 52))
                        .foregroundColor(.indigo)
                    Text("MeantByMe")
                        .font(.largeTitle.bold())
                    Text("耳机私密朗读，患者语音确认后再外放")
                        .multilineTextAlignment(.center)
                        .foregroundColor(.secondary)
                }

                Picker("会话模式", selection: $companion.mode) {
                    Text("替患者表达").tag(CompanionMode.expression)
                    Text("向 AI 提问").tag(CompanionMode.qa)
                }
                .pickerStyle(.segmented)
                .disabled(companion.sessionStarted)

                VStack(alignment: .leading, spacing: 12) {
                    Label(companion.headsetStatus, systemImage: "dot.radiowaves.left.and.right")
                    Label(companion.sessionStatus, systemImage: "waveform")
                    Label(companion.safetyStatus, systemImage: "checkmark.shield")
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
                .background(Color(.secondarySystemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 16))

                if !companion.headsetConnected {
                    Button("连接 Viaim 耳机") {
                        companion.connectHeadset()
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                } else if !companion.sessionStarted {
                    Button("开始陪伴") {
                        Task { await companion.startCompanion() }
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                } else {
                    Text("持续陪伴中。停顿 8 秒后自动补全；说“是/嗯”确认，说“不是/不对”更换。")
                        .font(.headline)
                        .multilineTextAlignment(.center)
                    Button("由陪护者结束会话", role: .destructive) {
                        Task { await companion.stopCompanion() }
                    }
                    .buttonStyle(.bordered)
                }

                Spacer()
                Text("候选只在耳机中播放；确认后也只使用系统中性音。")
                    .font(.footnote)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }
            .padding(24)
            .navigationBarHidden(true)
            .alert(
                "需要处理",
                isPresented: Binding(
                    get: { companion.errorMessage != nil },
                    set: { if !$0 { companion.errorMessage = nil } }
                )
            ) {
                Button("好", role: .cancel) {}
            } message: {
                Text(companion.errorMessage ?? "")
            }
        }
    }
}
