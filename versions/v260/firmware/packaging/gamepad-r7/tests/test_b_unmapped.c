#define _GNU_SOURCE
#include <assert.h>
#ifdef NDEBUG
#error This test requires enabled assertions
#endif
#define main bridge_application_main
#include "../gamesir-xboxd.c"
#undef main

static void check_event(const struct input_event *events, size_t count, int type, int code, int value) {
    for (size_t i=0;i<count;i++)
        if(events[i].type==type && events[i].code==code && events[i].value==value)return;
    fprintf(stderr,"missing event type=%d code=%d value=%d\n",type,code,value);
    assert(false);
}

int main(void) {
    int source[2],output[2];
    assert(pipe2(source,O_NONBLOCK|O_CLOEXEC)==0);
    assert(pipe2(output,O_NONBLOCK|O_CLOEXEC)==0);
    struct pollfd inputs[2]={{.fd=source[0],.events=POLLIN},{.fd=-1,.events=POLLIN}};
    struct mode_state mode={0};
    const struct axis_map maps[]={
      {.src=ABS_X,.dst=ABS_X,.in_min=-32768,.in_max=32767,.out_min=-32768,.out_max=32767},
      {.src=ABS_BRAKE,.dst=ABS_Z,.in_min=0,.in_max=255,.out_min=0,.out_max=255},
      {.src=ABS_GAS,.dst=ABS_RZ,.in_min=0,.in_max=255,.out_min=0,.out_max=255}
    };
    const struct input_event events[]={
      {.type=EV_KEY,.code=BTN_EAST,.value=1},
      {.type=EV_KEY,.code=BTN_START,.value=1},
      {.type=EV_KEY,.code=BTN_SOUTH,.value=1},
      {.type=EV_KEY,.code=BTN_NORTH,.value=1},
      {.type=EV_KEY,.code=BTN_WEST,.value=1},
      {.type=EV_KEY,.code=BTN_SELECT,.value=1},
      {.type=EV_KEY,.code=BTN_TL,.value=1},
      {.type=EV_KEY,.code=BTN_TR,.value=1},
      {.type=EV_KEY,.code=BTN_MODE,.value=1},
      {.type=EV_KEY,.code=BTN_MODE,.value=0},
      {.type=EV_KEY,.code=BTN_EAST,.value=0},
      {.type=EV_ABS,.code=ABS_X,.value=32767},
      {.type=EV_ABS,.code=ABS_BRAKE,.value=200},
      {.type=EV_ABS,.code=ABS_GAS,.value=220},
      {.type=EV_SYN,.code=SYN_REPORT,.value=0}
    };
    assert(write(source[1],events,sizeof(events))==sizeof(events));
    assert(poll(inputs,2,100)>0);
    assert(forward_ready_inputs(inputs,output[1],maps,3,&mode));
    struct input_event result[40];ssize_t bytes=read(output[0],result,sizeof(result));
    assert(bytes>0 && bytes%(ssize_t)sizeof(result[0])==0);size_t count=(size_t)bytes/sizeof(result[0]);
    for(size_t i=0;i<count;i++)assert(!(result[i].type==EV_KEY && result[i].code==BTN_EAST));
    int keys[]={BTN_START,BTN_SOUTH,BTN_NORTH,BTN_WEST,BTN_SELECT,BTN_TL,BTN_TR};
    for(size_t i=0;i<sizeof(keys)/sizeof(keys[0]);i++)check_event(result,count,EV_KEY,keys[i],1);
    check_event(result,count,EV_KEY,BTN_MODE,1);check_event(result,count,EV_KEY,BTN_MODE,0);
    check_event(result,count,EV_ABS,ABS_X,32767);check_event(result,count,EV_ABS,ABS_Z,200);check_event(result,count,EV_ABS,ABS_RZ,220);
    const struct input_event b_only[]={{.type=EV_KEY,.code=BTN_EAST,.value=1},{.type=EV_KEY,.code=BTN_EAST,.value=0},{.type=EV_SYN,.code=SYN_REPORT}};
    assert(write(source[1],b_only,sizeof(b_only))==sizeof(b_only));assert(poll(inputs,2,100)>0);
    assert(forward_ready_inputs(inputs,output[1],maps,3,&mode));bytes=read(output[0],result,sizeof(result));
    assert(bytes==sizeof(result[0]));check_event(result,1,EV_SYN,SYN_REPORT,0);
    close(source[0]);close(source[1]);close(output[0]);close(output[1]);
    puts("PASS production R7 event path: B press/release filtered; Start/Select/A/X/Y/LB/RB/HOME/stick/triggers preserved");
    return 0;
}
