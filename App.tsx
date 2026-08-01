import React, { useState, useEffect } from 'react';
import {
  StyleSheet,
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  PanResponder,
  ScrollView,
} from 'react-native';

const BACKEND_URI = "http://127.0.0.1:8000";

interface Message {
  role: 'user' | 'assistant';
  text: string;
}

export default function App() {
  const [apiKey, setApiKey] = useState("");
  const [apiUrl, setApiUrl] = useState("https://api.openai.com/v1/chat/completions");
  const [model, setModel] = useState("gpt-4-turbo");

  const [input, setInput] = useState("");
  const [history, setHistory] = useState<Message[]>([]);
  const [voiceMode, setVoiceMode] = useState(false);
  const [recording, setRecording] = useState(false);
  const [loading, setLoading] = useState(false);
  const [showConfig, setShowConfig] = useState(true);

  const [pos, setPos] = useState({ x: 0, y: 0 });

  // Pan handlers to allow smooth dragging of the borderless overlay window
  const dragResponder = PanResponder.create({
    onStartShouldSetPanResponder: () => true,
    onPanResponderMove: (_, gesture) => {
      setPos({ x: gesture.dx, y: gesture.dy });
    }
  });

  const saveConfiguration = async () => {
    if (!apiKey.trim()) return;
    try {
      const response = await fetch(`${BACKEND_URI}/configure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey, api_url: apiUrl, model_name: model })
      });
      if (response.ok) {
        setShowConfig(false);
      }
    } catch (err) {
      console.warn("Failed to communicate with system background services.");
    }
  };

  const dispatchPrompt = async (promptText: string) => {
    if (!promptText.trim()) return;
    const cache = [...history, { role: 'user' as const, text: promptText }];
    setHistory(cache);
    setInput("");
    setLoading(true);

    try {
      const response = await fetch(`${BACKEND_URI}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: promptText })
      });
      const data = await response.json();
      if (response.ok && data.answer) {
        setHistory([...cache, { role: 'assistant', text: data.answer }]);
      } else {
        throw new Error(data.detail || "Error processing prompt");
      }
    } catch (err: any) {
      setHistory([...cache, { role: 'assistant', text: `Failed: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  const toggleVoiceRecording = async () => {
    if (!recording) {
      try {
        const res = await fetch(`${BACKEND_URI}/voice/start`, { method: 'POST' });
        if (res.ok) setRecording(true);
      } catch (err) {
        console.warn("Audio hardware initialization failure.");
      }
    } else {
      setRecording(false);
      setLoading(true);
      try {
        const res = await fetch(`${BACKEND_URI}/voice/stop`, { method: 'POST' });
        const data = await res.json();
        if (data.transcription) {
          await dispatchPrompt(data.transcription);
        }
      } catch (err) {
        console.warn("Audio processing pipeline failure.");
      } finally {
        setLoading(false);
      }
    }
  };

  return (
    <View 
      style={[styles.canvas, { transform: [{ translateX: pos.x }, { translateY: pos.y }] }]}
      {...dragResponder.panHandlers}
    >
      <View style={styles.appHeader}>
        <Text style={styles.headerTitle}>✦ STEALTH UTILITY</Text>
        <TouchableOpacity style={styles.configBtn} onPress={() => setShowConfig(!showConfig)}>
          <Text style={styles.configBtnIcon}>{showConfig ? "✕" : "⚙"}</Text>
        </TouchableOpacity>
      </View>

      {showConfig ? (
        <ScrollView contentContainerStyle={styles.body}>
          <Text style={styles.fieldLabel}>Custom Model API Endpoint</Text>
          <TextInput 
            style={styles.fieldInput}
            value={apiUrl}
            onChangeText={setApiUrl}
            placeholder="https://your-custom-host/v1"
            placeholderTextColor="#475569"
          />

          <Text style={styles.fieldLabel}>Authentication Key</Text>
          <TextInput 
            style={styles.fieldInput}
            value={apiKey}
            onChangeText={setApiKey}
            secureTextEntry
            placeholder="Paste system API key"
            placeholderTextColor="#475569"
          />

          <Text style={styles.fieldLabel}>Model Name Identifier</Text>
          <TextInput 
            style={styles.fieldInput}
            value={model}
            onChangeText={setModel}
            placeholder="gpt-4-turbo"
            placeholderTextColor="#475569"
          />

          <TouchableOpacity style={styles.actionBtn} onPress={saveConfiguration}>
            <Text style={styles.actionBtnText}>Save Connection</Text>
          </TouchableOpacity>
        </ScrollView>
      ) : (
        <View style={styles.body}>
          <ScrollView style={styles.messageScroll}>
            {history.length === 0 ? (
              <View style={styles.panelPlaceholder}>
                <Text style={styles.placeholderText}>Ready for Input</Text>
              </View>
            ) : (
              history.map((msg, index) => (
                <View 
                  key={index}
                  style={[styles.bubble, msg.role === 'user' ? styles.bubbleUser : styles.bubbleAi]}
                >
                  <Text style={styles.bubbleText}>{msg.text}</Text>
                </View>
              ))
            )}
            {loading && <ActivityIndicator size="small" color="#818cf8" style={styles.spinner} />}
          </ScrollView>

          {voiceMode ? (
            <View style={styles.recordingArea}>
              <TouchableOpacity 
                style={[styles.recordBtn, recording && styles.recordBtnActive]}
                onPress={toggleVoiceRecording}
              >
                <Text style={styles.recordBtnText}>{recording ? "■" : "🎤"}</Text>
              </TouchableOpacity>
              <Text style={styles.statusLabel}>
                {recording ? "Recording System Audio..." : "Click to Speak"}
              </Text>
            </View>
          ) : (
            <View style={styles.textEntryArea}>
              <TextInput 
                style={[styles.fieldInput, styles.inlineInput]}
                value={input}
                onChangeText={setInput}
                placeholder="Ask your model..."
                placeholderTextColor="#475569"
                onSubmitEditing={() => dispatchPrompt(input)}
              />
              <TouchableOpacity style={styles.sendIconBtn} onPress={() => dispatchPrompt(input)}>
                <Text style={styles.sendIconText}>➔</Text>
              </TouchableOpacity>
            </View>
          )}

          <View style={styles.navRow}>
            <TouchableOpacity 
              style={[styles.navBtn, !voiceMode && styles.navBtnActive]}
              onPress={() => setVoiceMode(false)}
            >
              <Text style={styles.navBtnText}>Text Interface</Text>
            </TouchableOpacity>
            <TouchableOpacity 
              style={[styles.navBtn, voiceMode && styles.navBtnActive]}
              onPress={() => setVoiceMode(true)}
            >
              <Text style={styles.navBtnText}>Voice Control</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  canvas: {
    width: 350,
    backgroundColor: '#090d16',
    borderWidth: 1,
    borderColor: '#1e293b',
    borderRadius: 14,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.5,
    shadowRadius: 16,
    overflow: 'hidden',
  },
  appHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#1e293b',
    backgroundColor: '#0b1329',
  },
  headerTitle: {
    color: '#818cf8',
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 1.5,
  },
  configBtn: {
    padding: 2,
  },
  configBtnIcon: {
    color: '#64748b',
    fontSize: 14,
  },
  body: {
    padding: 16,
  },
  fieldLabel: {
    color: '#94a3b8',
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  fieldInput: {
    backgroundColor: '#020617',
    borderWidth: 1,
    borderColor: '#1e293b',
    borderRadius: 8,
    color: '#f8fafc',
    fontSize: 12,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginBottom: 14,
  },
  actionBtn: {
    backgroundColor: '#4f46e5',
    paddingVertical: 10,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: 4,
  },
  actionBtnText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: '700',
  },
  messageScroll: {
    height: 180,
    marginBottom: 14,
  },
  panelPlaceholder: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingTop: 60,
  },
  placeholderText: {
    color: '#334155',
    fontSize: 11,
    fontWeight: '600',
  },
  bubble: {
    padding: 10,
    borderRadius: 8,
    marginVertical: 4,
    maxWidth: '85%',
  },
  bubbleUser: {
    backgroundColor: '#2563eb',
    alignSelf: 'flex-end',
  },
  bubbleAi: {
    backgroundColor: '#1e293b',
    alignSelf: 'flex-start',
  },
  bubbleText: {
    color: '#f8fafc',
    fontSize: 12,
  },
  spinner: {
    marginVertical: 10,
  },
  textEntryArea: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
    gap: 8,
  },
  inlineInput: {
    flex: 1,
    marginBottom: 0,
  },
  sendIconBtn: {
    backgroundColor: '#818cf8',
    width: 32,
    height: 32,
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sendIconText: {
    color: '#0f172a',
    fontWeight: 'bold',
  },
  recordingArea: {
    alignItems: 'center',
    marginBottom: 14,
  },
  recordBtn: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: 'rgba(129, 140, 248, 0.15)',
    borderWidth: 1,
    borderColor: '#818cf8',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 6,
  },
  recordBtnActive: {
    backgroundColor: '#ef4444',
    borderColor: '#ef4444',
  },
  recordBtnText: {
    color: '#fff',
    fontSize: 16,
  },
  statusLabel: {
    color: '#475569',
    fontSize: 10,
    fontWeight: '600',
  },
  navRow: {
    flexDirection: 'row',
    backgroundColor: '#020617',
    borderRadius: 6,
    padding: 3,
  },
  navBtn: {
    flex: 1,
    paddingVertical: 6,
    alignItems: 'center',
    borderRadius: 4,
  },
  navBtnActive: {
    backgroundColor: '#1e293b',
  },
  navBtnText: {
    color: '#cbd5e1',
    fontSize: 10,
    fontWeight: '700',
  }
});