// OBEYA Video Player — self-contained Windows launcher.
// Built with .NET Framework's own C# compiler; no Python/Node/Internet required.
// Video, HTML, and the original icon are embedded as manifest resources.
// No MP4 is extracted to disk at runtime: byte-range streaming over 127.0.0.1 only.
using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Text;
using System.Threading;
using System.Windows.Forms;

internal static class OBEYALauncher
{
    private static readonly Assembly Embedded = Assembly.GetExecutingAssembly();
    private static TcpListener Listener;
    private static volatile bool Running = true;
    private static long LastActivityTicks = DateTime.UtcNow.Ticks;
    private static long VideoOffset;
    private static long VideoLength;
    private static string ExePath = Assembly.GetExecutingAssembly().Location;

    [STAThread]
    private static void Main()
    {
        try
        {
            ReadEmbeddedVideoFooter();
            Listener = new TcpListener(IPAddress.Loopback, 0);
            Listener.Start(32);
            int port = ((IPEndPoint)Listener.LocalEndpoint).Port;
            Thread listenerThread = new Thread(AcceptConnections);
            listenerThread.IsBackground = true;
            listenerThread.Name = "OBEYA local media server";
            listenerThread.Start();

            string address = "http://127.0.0.1:" + port.ToString() + "/";
            if (!OpenBrowser(address))
            {
                MessageBox.Show("Microsoft Edge or Google Chrome could not be started.\nPlease install or enable a supported browser.", "OBEYA Video Player", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            // The HTML page sends a local heartbeat while it is open.
            // When the browser window is closed, the EXE exits without leaving a tray process.
            while (Running)
            {
                Thread.Sleep(3000);
                long since = DateTime.UtcNow.Ticks - Interlocked.Read(ref LastActivityTicks);
                if (since > TimeSpan.FromMinutes(8).Ticks) Running = false;
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show("OBEYA Video Player could not start:\n" + ex.Message, "OBEYA Video Player", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
        finally
        {
            Running = false;
            try { if (Listener != null) Listener.Stop(); } catch { }
        }
    }

    private static bool OpenBrowser(string address)
    {
        // First try the genuine Windows browser EXE in its normal locations.
        string pf = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        string x86 = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86);
        string lad = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);

        string[] candidates = new string[] {
            Path.Combine(pf,  @"Microsoft\Edge\Application\msedge.exe"),
            Path.Combine(x86, @"Microsoft\Edge\Application\msedge.exe"),
            Path.Combine(lad, @"Microsoft\Edge\Application\msedge.exe"),
            Path.Combine(pf,  @"Google\Chrome\Application\chrome.exe"),
            Path.Combine(x86, @"Google\Chrome\Application\chrome.exe"),
            Path.Combine(lad, @"Google\Chrome\Application\chrome.exe"),
            "msedge.exe", "chrome.exe"
        };
        foreach (string candidate in candidates)
        {
            try
            {
                if (Path.IsPathRooted(candidate) && !File.Exists(candidate)) continue;
                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = candidate;
                psi.Arguments = "--app=\"" + address + "\" --new-window";
                psi.UseShellExecute = true;
                Process.Start(psi);
                return true;
            }
            catch { }
        }

        // Last resort: browser registered as default (no app-window guarantee).
        try
        {
            ProcessStartInfo fallback = new ProcessStartInfo();
            fallback.FileName = address;
            fallback.UseShellExecute = true;
            Process.Start(fallback);
            return true;
        }
        catch { return false; }
    }

    private static void AcceptConnections()
    {
        while (Running)
        {
            try
            {
                TcpClient connection = Listener.AcceptTcpClient();
                ThreadPool.QueueUserWorkItem(delegate(object state) { ProcessConnection((TcpClient)state); }, connection);
            }
            catch (SocketException) { if (!Running) break; }
            catch (ObjectDisposedException) { break; }
            catch { }
        }
    }

    private static void ProcessConnection(TcpClient client)
    {
        using (client)
        {
            try
            {
                client.NoDelay = true;
                client.ReceiveTimeout = 12000;
                client.SendTimeout = 30000;
                using (NetworkStream stream = client.GetStream())
                using (StreamReader reader = new StreamReader(stream, Encoding.ASCII, false, 4096, true))
                {
                    string line = reader.ReadLine();
                    if (string.IsNullOrEmpty(line)) return;
                    string[] parts = line.Split(' ');
                    if (parts.Length < 2) return;
                    string method = parts[0].ToUpperInvariant();
                    string path = parts[1].Split('?')[0];
                    string range = null;

                    while (true)
                    {
                        string header = reader.ReadLine();
                        if (header == null || header.Length == 0) break;
                        if (header.StartsWith("Range:", StringComparison.OrdinalIgnoreCase))
                            range = header.Substring(6).Trim();
                    }
                    Interlocked.Exchange(ref LastActivityTicks, DateTime.UtcNow.Ticks);

                    if (method != "GET" && method != "HEAD")
                    {
                        SendText(stream, "405 Method Not Allowed", "Method not supported.", method == "HEAD");
                        return;
                    }
                    if (path == "/ping")
                    {
                        SendHeaders(stream, "204 No Content", "text/plain", 0, null, false);
                        return;
                    }
                    if (path == "/" || path == "/index.html" || path == "/OBEYA.html")
                    {
                        ServeResource(stream, "ObeyaHTML", "text/html; charset=utf-8", null, method == "HEAD");
                        return;
                    }
                    if (path == "/video.mp4" || path == "/OBEYA.mp4")
                    {
                        ServeOriginalVideo(stream, range, method == "HEAD");
                        return;
                    }
                    if (path == "/favicon.ico")
                    {
                        ServeResource(stream, "ObeyaIcon", "image/x-icon", null, method == "HEAD");
                        return;
                    }
                    SendText(stream, "404 Not Found", "File not found.", method == "HEAD");
                }
            }
            catch (IOException) { }
            catch (ObjectDisposedException) { }
            catch (Exception) { }
        }
    }

    private static void ServeResource(NetworkStream target, string name, string mediaType, string range, bool headOnly)
    {
        using (Stream source = Embedded.GetManifestResourceStream(name))
        {
            if (source == null)
            {
                SendText(target, "500 Internal Server Error", "Missing embedded resource: " + name, headOnly);
                return;
            }

            long total = source.Length, start = 0, end = total - 1;
            bool isVideo = name == "ObeyaVideo";
            bool partial = isVideo && !string.IsNullOrEmpty(range);
            if (partial && !ParseRange(range, total, out start, out end))
            {
                string headers = "Content-Range: bytes */" + total.ToString() + "\r\n";
                SendHeaders(target, "416 Range Not Satisfiable", mediaType, 0, headers, true);
                return;
            }
            long length = end - start + 1;
            string extra = "Accept-Ranges: bytes\r\nCache-Control: private, max-age=0\r\n";
            if (partial) extra += "Content-Range: bytes " + start.ToString() + "-" + end.ToString() + "/" + total.ToString() + "\r\n";
            SendHeaders(target, partial ? "206 Partial Content" : "200 OK", mediaType, length, extra, isVideo);
            if (headOnly) return;

            source.Seek(start, SeekOrigin.Begin);
            byte[] buffer = new byte[128 * 1024];
            long remaining = length;
            while (remaining > 0)
            {
                int count = source.Read(buffer, 0, (int)Math.Min(buffer.Length, remaining));
                if (count <= 0) break;
                target.Write(buffer, 0, count);
                remaining -= count;
            }
        }
    }

    // The original MP4 is appended verbatim to the Windows PE file in an overlay,
    // followed by an 8-byte marker, 64-bit video start, and 64-bit video length.
    // This avoids compiling 410+ MB as a resource, and never extracts the MP4 to disk.
    private static void ReadEmbeddedVideoFooter()
    {
        using (FileStream file = new FileStream(ExePath, FileMode.Open, FileAccess.Read, FileShare.Read))
        {
            if (file.Length < 24) throw new InvalidDataException("The OBEYA video is not included in this EXE.");
            file.Seek(-24, SeekOrigin.End);
            using (BinaryReader reader = new BinaryReader(file, Encoding.ASCII))
            {
                byte[] marker = reader.ReadBytes(8);
                if (Encoding.ASCII.GetString(marker) != "OBEYAV01")
                    throw new InvalidDataException("This launcher does not contain the OBEYA video. Please build the full EXE.");
                long offset = reader.ReadInt64();
                long length = reader.ReadInt64();
                if (offset <= 0 || length <= 0 || offset > file.Length - 24 || length != file.Length - offset - 24)
                    throw new InvalidDataException("The embedded OBEYA video is incomplete.");
                VideoOffset = offset;
                VideoLength = length;
            }
        }
    }

    private static void ServeOriginalVideo(NetworkStream target, string range, bool headOnly)
    {
        long begin = 0, end = VideoLength - 1;
        bool partial = !String.IsNullOrEmpty(range);
        if (partial && !ParseRange(range, VideoLength, out begin, out end))
        {
            SendHeaders(target, "416 Range Not Satisfiable", "video/mp4", 0,
                "Content-Range: bytes */" + VideoLength.ToString() + "\r\n", true);
            return;
        }

        long remaining = end - begin + 1;
        string headers = "Cache-Control: private, max-age=0\r\n";
        if (partial) headers += "Content-Range: bytes " + begin.ToString() + "-" +
            end.ToString() + "/" + VideoLength.ToString() + "\r\n";
        SendHeaders(target, partial ? "206 Partial Content" : "200 OK", "video/mp4",
            remaining, headers, true);
        if (headOnly) return;

        using (FileStream file = new FileStream(ExePath, FileMode.Open, FileAccess.Read, FileShare.Read))
        {
            file.Seek(VideoOffset + begin, SeekOrigin.Begin);
            byte[] buffer = new byte[131072];
            while (remaining > 0)
            {
                int read = file.Read(buffer, 0, (int)Math.Min(buffer.Length, remaining));
                if (read <= 0) break;
                target.Write(buffer, 0, read);
                remaining -= read;
            }
        }
    }

    private static bool ParseRange(string header, long total, out long first, out long last)
    {
        first = 0; last = total - 1;
        if (total <= 0 || !header.StartsWith("bytes=", StringComparison.OrdinalIgnoreCase)) return false;
        string value = header.Substring(6).Trim();
        if (value.IndexOf(',') >= 0) return false; // MP4 uses single byte ranges
        int dash = value.IndexOf('-');
        if (dash < 0) return false;
        string a = value.Substring(0, dash).Trim(), b = value.Substring(dash + 1).Trim();
        long v;
        if (a.Length == 0)
        {
            if (!long.TryParse(b, out v) || v < 1) return false;
            first = Math.Max(0, total - v);
        }
        else
        {
            if (!long.TryParse(a, out v) || v < 0 || v >= total) return false;
            first = v;
            if (b.Length > 0)
            {
                if (!long.TryParse(b, out v) || v < first) return false;
                last = Math.Min(v, total - 1);
            }
        }
        return first >= 0 && first <= last && last < total;
    }

    private static void SendText(NetworkStream stream, string status, string message, bool headOnly)
    {
        byte[] data = Encoding.UTF8.GetBytes(message);
        SendHeaders(stream, status, "text/plain; charset=utf-8", data.Length, null, false);
        if (!headOnly) stream.Write(data, 0, data.Length);
    }

    private static void SendHeaders(NetworkStream stream, string status, string mediaType, long length, string extras, bool video)
    {
        string response = "HTTP/1.1 " + status + "\r\n" +
            "Content-Type: " + mediaType + "\r\n" +
            "Content-Length: " + length.ToString() + "\r\n" +
            "Connection: close\r\n" +
            "X-Content-Type-Options: nosniff\r\n" +
            "Access-Control-Allow-Origin: http://127.0.0.1\r\n" +
            (video ? "Accept-Ranges: bytes\r\n" : "") +
            (extras ?? "") +
            "\r\n";
        byte[] data = Encoding.ASCII.GetBytes(response);
        stream.Write(data, 0, data.Length);
    }
}
