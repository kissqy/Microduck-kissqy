/* OpenSSH callback. No GUI or command-line password; write UTF-8 to its pipe.
 * Build: zig cc -target x86_64-windows-gnu -Os -s -nostdlib
 *        -isystem <zig-lib>/libc/include/any-windows-any
 *        -Wl,--entry=start -Wl,--subsystem=windows this.c -lkernel32 -o ../console/ssh-askpass.exe
 */
#include <windows.h>
void start(void) {
    static WCHAR password[1025];
    static char encoded[4096];
    DWORD written;
    DWORD size = GetEnvironmentVariableW(L"MICRODUCK_SSH_PASSWORD", password, 1025);
    if (!size || size >= 1025) ExitProcess(1);
    int bytes = WideCharToMultiByte(CP_UTF8, 0, password, size, encoded, 4095, NULL, NULL);
    if (!bytes) ExitProcess(1);
    encoded[bytes++] = '\n';
    BOOL okay = WriteFile(GetStdHandle(STD_OUTPUT_HANDLE), encoded, bytes, &written, NULL);
    SecureZeroMemory(password, sizeof(password));
    SecureZeroMemory(encoded, sizeof(encoded));
    ExitProcess(okay && written == (DWORD)bytes ? 0 : 1);
}
