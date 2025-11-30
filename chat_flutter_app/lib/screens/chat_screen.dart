// lib/screens/chat_screen.dart
import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:http/http.dart' as http;
import 'package:file_picker/file_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'package:open_filex/open_filex.dart';
import 'package:dio/dio.dart';

class ChatScreen extends StatefulWidget {
  final String nickname;
  const ChatScreen({super.key, required this.nickname});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  late WebSocketChannel channel;
  final TextEditingController _msgController = TextEditingController();
  final ScrollController _scrollController =
      ScrollController(); // ✅ أضفت ScrollController
  final List<Map<String, dynamic>> _messages = [];
  final List<String> _files = [];
  bool _isConnected = false;

  // ✅ استخدم IP الصحيح (192.168.1.2 من ipconfig)
  final String baseUrl = "http://192.168.1.2:8000";
  final String wsUrl = "ws://192.168.1.2:8000/ws";

  @override
  void initState() {
    super.initState();
    connectWebSocket();
    fetchFiles(); // جلب الملفات عند فتح الشات
  }

  void connectWebSocket() {
    try {
      channel = WebSocketChannel.connect(
        Uri.parse("$wsUrl/${widget.nickname}"),
      );

      setState(() => _isConnected = true);

      channel.stream.listen(
        (data) {
          print("✅ رسالة وصلت: $data");

          setState(() {
            final msg = data.toString().trim();
            if (msg.isEmpty) return;

            // رسائل النظام
            if (msg.contains("joined the chat") ||
                msg.contains("left the chat") ||
                msg.contains("Welcome") ||
                msg.contains("Recent Messages") ||
                msg.contains("---")) {
              _messages.add({"type": "system", "content": msg});
            }
            // رسائل عادية
            else {
              _messages.add({"type": "message", "content": msg});
            }
          });

          // ✅ Scroll لآخر رسالة بطريقة صحيحة
          _scrollToBottom();
        },
        onDone: () {
          print("❌ WebSocket مغلق");
          setState(() => _isConnected = false);
          _showSnackBar("انقطع الاتصال بالسيرفر", isError: true);
        },
        onError: (error) {
          print("❌ خطأ WebSocket: $error");
          setState(() => _isConnected = false);
          _showSnackBar("خطأ في الاتصال: $error", isError: true);
        },
      );
    } catch (e) {
      print("❌ فشل الاتصال: $e");
      _showSnackBar("فشل الاتصال بالسيرفر: $e", isError: true);
    }
  }

  // ✅ دالة محسّنة للـ scroll
  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void sendMessage() {
    if (_msgController.text.trim().isEmpty || !_isConnected) {
      _showSnackBar("لا يمكن إرسال رسالة فارغة", isError: true);
      return;
    }

    final message = _msgController.text.trim();

    try {
      channel.sink.add(message);
      print("📤 أرسلت: $message");

      // إضافة الرسالة محلياً
      setState(() {
        _messages.add({
          "type": "message",
          "content": "${widget.nickname}: $message",
        });
      });

      _msgController.clear();
      _scrollToBottom();
    } catch (e) {
      print("❌ فشل إرسال الرسالة: $e");
      _showSnackBar("فشل إرسال الرسالة", isError: true);
    }
  }

  Future<void> uploadFile() async {
    FilePickerResult? result = await FilePicker.platform.pickFiles();
    if (result == null) return;

    File file = File(result.files.single.path!);
    String fileName = result.files.single.name;

    try {
      _showSnackBar("جاري رفع $fileName...");

      var dio = Dio();
      FormData formData = FormData.fromMap({
        "file": await MultipartFile.fromFile(file.path, filename: fileName),
      });

      await dio.post("$baseUrl/ftp/upload", data: formData);
      _showSnackBar("✅ تم رفع $fileName بنجاح");
      fetchFiles();
    } catch (e) {
      print("❌ فشل رفع الملف: $e");
      _showSnackBar("فشل رفع الملف", isError: true);
    }
  }

  Future<void> fetchFiles() async {
    try {
      final response = await http.get(Uri.parse("$baseUrl/ftp/list"));
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        setState(() {
          _files.clear();
          _files.addAll(List<String>.from(data["files"] ?? []));
        });
      }
    } catch (e) {
      print("❌ فشل جلب الملفات: $e");
    }
  }

  Future<void> downloadFile(String filename) async {
    try {
      _showSnackBar("جاري تحميل $filename...");

      final dir = await getTemporaryDirectory();
      final filePath = "${dir.path}/$filename";
      await Dio().download("$baseUrl/ftp/download/$filename", filePath);

      _showSnackBar("✅ تم التحميل بنجاح");
      OpenFilex.open(filePath);
    } catch (e) {
      print("❌ فشل تحميل الملف: $e");
      _showSnackBar("فشل تحميل الملف", isError: true);
    }
  }

  void _showSnackBar(String message, {bool isError = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: isError ? Colors.red : Colors.green,
        duration: const Duration(seconds: 2),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            // ✅ مؤشر الاتصال
            Container(
              width: 10,
              height: 10,
              decoration: BoxDecoration(
                color: _isConnected ? Colors.green : Colors.red,
                shape: BoxShape.circle,
              ),
            ),
            const SizedBox(width: 8),
            Text("الدردشة - ${widget.nickname}"),
          ],
        ),
        backgroundColor: Colors.deepPurple,
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: const Icon(Icons.cloud_upload),
            onPressed: uploadFile,
            tooltip: "رفع ملف",
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: fetchFiles,
            tooltip: "تحديث الملفات",
          ),
        ],
      ),
      body: Column(
        children: [
          // قائمة الملفات
          if (_files.isNotEmpty)
            Container(
              height: 80,
              color: Colors.grey[100],
              child: ListView.builder(
                scrollDirection: Axis.horizontal,
                itemCount: _files.length,
                itemBuilder: (ctx, i) => Card(
                  margin: const EdgeInsets.all(8),
                  child: InkWell(
                    onTap: () => downloadFile(_files[i]),
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Row(
                        children: [
                          const Icon(
                            Icons.attach_file,
                            color: Colors.deepPurple,
                          ),
                          const SizedBox(width: 5),
                          Text(
                            _files[i],
                            style: const TextStyle(fontWeight: FontWeight.bold),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),

          // قائمة الرسائل ✅ مع ScrollController
          Expanded(
            child: ListView.builder(
              controller: _scrollController, // ✅ هنا المفتاح
              padding: const EdgeInsets.all(10),
              itemCount: _messages.length,
              itemBuilder: (ctx, i) {
                final msg = _messages[i];
                final bool isMe = msg["content"].toString().startsWith(
                  "${widget.nickname}:",
                );

                // رسائل النظام
                if (msg["type"] == "system") {
                  return Center(
                    child: Padding(
                      padding: const EdgeInsets.all(8.0),
                      child: Text(
                        msg["content"],
                        style: const TextStyle(
                          color: Colors.grey,
                          fontSize: 12,
                          fontStyle: FontStyle.italic,
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ),
                  );
                }

                // رسائل عادية
                return Align(
                  alignment: isMe
                      ? Alignment.centerRight
                      : Alignment.centerLeft,
                  child: Container(
                    margin: const EdgeInsets.symmetric(
                      vertical: 4,
                      horizontal: 8,
                    ),
                    padding: const EdgeInsets.all(14),
                    constraints: BoxConstraints(
                      maxWidth: MediaQuery.of(context).size.width * 0.7,
                    ),
                    decoration: BoxDecoration(
                      color: isMe ? Colors.deepPurple[100] : Colors.grey[200],
                      borderRadius: BorderRadius.circular(18),
                    ),
                    child: Text(
                      msg["content"],
                      style: TextStyle(
                        color: isMe ? Colors.deepPurple[900] : Colors.black87,
                      ),
                    ),
                  ),
                );
              },
            ),
          ),

          // شريط الإدخال
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.grey[50],
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.1),
                  blurRadius: 4,
                  offset: const Offset(0, -2),
                ),
              ],
            ),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _msgController,
                    enabled: _isConnected,
                    decoration: InputDecoration(
                      hintText: _isConnected
                          ? "اكتب رسالتك هنا..."
                          : "غير متصل...",
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(25),
                      ),
                      filled: true,
                      fillColor: Colors.white,
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 20,
                        vertical: 10,
                      ),
                    ),
                    onSubmitted: (_) => sendMessage(),
                  ),
                ),
                const SizedBox(width: 8),
                FloatingActionButton(
                  onPressed: _isConnected ? sendMessage : null,
                  backgroundColor: _isConnected
                      ? Colors.deepPurple
                      : Colors.grey,
                  child: const Icon(Icons.send, color: Colors.white),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    channel.sink.close();
    _msgController.dispose();
    _scrollController.dispose(); // ✅ لا تنسى dispose
    super.dispose();
  }
}
