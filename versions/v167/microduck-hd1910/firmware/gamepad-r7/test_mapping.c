#define main bridge_main
#include "gamesir-xboxd.c"
#undef main
#include <assert.h>
int main(void) {
 assert(xbox_key(BTN_START)); assert(xbox_key(BTN_MODE));
 assert(!xbox_key(BTN_TR2)); assert(!xbox_key(BTN_TL2));
 assert(!xbox_key(KEY_MENU)); assert(!xbox_key(KEY_HOMEPAGE));
 struct axis_map trigger={.in_min=0,.in_max=1023,.out_min=0,.out_max=255};
 assert(scaled(&trigger,-1)==0); assert(scaled(&trigger,1023)==255);
 assert(scaled(&trigger,2048)==255);
 puts("PASS R7 menu/trigger isolation and axis scaling");
 return 0;
}
