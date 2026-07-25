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
                    Label(
                        "当前用户：\(companion.selectedProfileLabel)",
                        systemImage: "person.crop.circle"
                    )
                    Label(companion.headsetStatus, systemImage: "dot.radiowaves.left.and.right")
                    Label(companion.sessionStatus, systemImage: "waveform")
                    Label(companion.safetyStatus, systemImage: "checkmark.shield")
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
                .background(Color(.secondarySystemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 16))

                if companion.expressionTimerVisible {
                    HStack(spacing: 16) {
                        Image(
                            systemName: companion.expressionTimerActive
                                ? "waveform.circle.fill"
                                : "checkmark.circle.fill"
                        )
                        .font(.system(size: 34))
                        .foregroundColor(
                            companion.expressionTimerActive
                                ? .indigo
                                : .green
                        )

                        VStack(alignment: .leading, spacing: 3) {
                            Text(
                                companion.expressionTimerActive
                                    ? "本次表达正在计时"
                                    : "本次表达计时结束"
                            )
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            Text(
                                "\(companion.expressionElapsedSeconds) 秒"
                            )
                            .font(.system(size: 30, weight: .bold))
                            .monospacedDigit()
                        }
                        Spacer()
                    }
                    .padding()
                    .background(Color(.secondarySystemBackground))
                    .clipShape(RoundedRectangle(cornerRadius: 16))
                }

                if !companion.headsetConnected {
                    Button("连接 Viaim 耳机") {
                        companion.connectHeadset()
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                } else if !companion.sessionStarted {
                    VStack(spacing: 12) {
                        Button("开始陪伴") {
                            Task { await companion.startCompanion() }
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.large)

                        Button {
                            Task {
                                await companion.beginSpeakerVolumeTest()
                            }
                        } label: {
                            Label(
                                "测试并调节手机扬声器",
                                systemImage: "speaker.wave.3.fill"
                            )
                        }
                        .buttonStyle(.bordered)
                    }
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
            .overlay(alignment: .topTrailing) {
                Button {
                    companion.userSettingsPresented = true
                } label: {
                    Image(systemName: "gearshape.fill")
                        .font(.title3)
                        .padding(10)
                }
                .accessibilityLabel("用户设置")
            }
            .sheet(
                isPresented: $companion.speakerVolumeTestPresented,
                onDismiss: {
                    companion.endSpeakerVolumeTest()
                }
            ) {
                SpeakerVolumeTestView()
                    .environmentObject(companion)
            }
            .sheet(isPresented: $companion.userSettingsPresented) {
                UserSettingsView()
                    .environmentObject(companion)
            }
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

private struct SpeakerVolumeTestView: View {
    @EnvironmentObject private var companion: CompanionViewModel

    var body: some View {
        NavigationView {
            VStack(spacing: 28) {
                Image(systemName: "iphone.radiowaves.left.and.right")
                    .font(.system(size: 64))
                    .foregroundColor(.indigo)

                VStack(spacing: 8) {
                    Text("手机扬声器音量")
                        .font(.title2.bold())
                    Text("当前已临时切换到 iPhone 扬声器。拖动滑块，或使用手机音量键调节。")
                        .multilineTextAlignment(.center)
                        .foregroundColor(.secondary)
                }

                HStack(spacing: 12) {
                    Image(systemName: "speaker.fill")
                    SystemVolumeSlider()
                        .frame(height: 36)
                    Image(systemName: "speaker.wave.3.fill")
                }
                .padding()
                .background(Color(.secondarySystemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 16))

                Button {
                    companion.repeatSpeakerVolumeTest()
                } label: {
                    Label("再次播放测试语音", systemImage: "play.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)

                Text("测试结束后会恢复耳机路由。正式确认内容仍会自动切换到手机扬声器播放。")
                    .font(.footnote)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)

                Spacer()
            }
            .padding(24)
            .navigationTitle("扬声器测试")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("完成") {
                        companion.endSpeakerVolumeTest()
                    }
                }
            }
        }
    }
}
