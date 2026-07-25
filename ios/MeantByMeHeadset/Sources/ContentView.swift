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
                    Text("让话说完，让我做主")
                        .multilineTextAlignment(.center)
                        .foregroundColor(.secondary)
                }

                Picker("会话模式", selection: $companion.mode) {
                    Text("替你表达").tag(CompanionMode.expression)
                    Text("与你对话").tag(CompanionMode.qa)
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
                                    ? "\(companion.currentRoundLabel)正在计时"
                                    : "\(companion.currentRoundLabel)计时结束"
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
                    Text(companion.activeGuidance)
                        .font(.headline)
                        .multilineTextAlignment(.center)

                    VStack(spacing: 12) {
                        Button {
                            companion.finishSpeaking()
                        } label: {
                            Label(
                                "我说完了",
                                systemImage: "checkmark.circle.fill"
                            )
                            .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.large)
                        .disabled(!companion.canFinishSpeaking)
                        .accessibilityHint(
                            "结束当前录音并立即交给模型理解处理"
                        )

                        Button {
                            Task {
                                await companion.cancelCurrentExpression()
                            }
                        } label: {
                            Label(
                                companion.cancelActionLabel,
                                systemImage: "xmark.circle.fill"
                            )
                            .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(.orange)
                        .controlSize(.large)
                        .disabled(!companion.canCancelCurrentExpression)
                        .accessibilityHint(
                            companion.mode == .qa
                                ? "丢弃当前问题和回答并继续陪伴，不会进入后续对话上下文"
                                : "丢弃当前这句话并继续陪伴，不会确认、外放或写入记忆"
                        )

                        Text(companion.cancelGuidance)
                            .font(.footnote)
                            .foregroundColor(.secondary)

                        Button("由陪护者结束会话", role: .destructive) {
                            Task { await companion.stopCompanion() }
                        }
                        .buttonStyle(.bordered)
                    }
                }

                Spacer()
                Text("预测的完整句子将先在耳机中播放，经你确认后再在手机扬声器播放")
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
                    Text("如果当前为静音，系统会先跳过测试语音；调高音量后点击“再次播放测试语音”。")
                        .font(.footnote)
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
