/* Bounded read-only libmGBA transport; normal controller inputs only. */
#include <mgba/core/core.h>
#include <mgba/core/interface.h>
#include <mgba/core/log.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
static volatile int crashed;
static void crash(void *p){(void)p;crashed=1;}
static void silent(struct mLogger *l,int c,enum mLogLevel v,const char *fmt,va_list a){
    (void)l;(void)c;(void)v;(void)fmt;(void)a;
}
static struct mLogger logger={.log=silent};
static int range(unsigned a,unsigned n,unsigned lo,unsigned hi){
    return n && a>=lo && a<hi && n<=hi-a;
}
/* Fixed private path in the per-process working directory. No path argument. */
static int state_io(struct mCore *c,int save){
    const char *path="checkpoint.bin";
    size_t n=c->stateSize(c);
    if(!n||n>2u*1024u*1024u)return 0;
    void *buf=malloc(n);if(!buf)return 0;
    int ok=0;FILE *f=NULL;
    if(save){
        if(c->saveState(c,buf)&&(f=fopen(path,"wb"))!=NULL){
            ok=fwrite(buf,1,n,f)==n;
            if(fclose(f))ok=0;
        }
    }else if((f=fopen(path,"rb"))!=NULL){
        ok=fread(buf,1,n,f)==n&&fgetc(f)==EOF&&!ferror(f);
        if(fclose(f))ok=0;
        if(ok)ok=c->loadState(c,buf);
    }
    free(buf);return ok;
}
int main(int argc,char **argv){
    if(argc!=2)return 2;
    FILE *rom=fopen(argv[1],"rb");
    if(!rom)return 2;
    if(fseek(rom,0,SEEK_END)){fclose(rom);return 2;}
    long size=ftell(rom);fclose(rom);
    if(size<=0 || size>0x2000000)return 2;
    mLogSetDefaultLogger(&logger);
    struct mCore *c=mCoreFind(argv[1]);
    if(!c||!c->init(c))return 3;
    mCoreInitConfig(c,"gba-live");
    if(!mCoreLoadFile(c,argv[1])){c->deinit(c);return 3;}
    unsigned w=0,h=0;
    c->desiredVideoDimensions(c,&w,&h);
    if(w!=240||h!=160){c->deinit(c);return 3;}
    color_t *video=calloc((size_t)w*h,sizeof(*video));
    if(!video){c->deinit(c);return 3;}
    c->setVideoBuffer(c,video,w);
    struct mCoreCallbacks cb={0};cb.coreCrashed=crash;
    c->addCoreCallbacks(c,&cb);c->reset(c);
    unsigned frames=0;char line[128],extra;
    puts("READY");fflush(stdout);
    while(fgets(line,sizeof(line),stdin)){
        unsigned a,n;
        if(crashed){puts("ERR crash");fflush(stdout);break;}
        if(!strcmp(line,"QUIT\n"))break;
        if(!strcmp(line,"SAVE\n")||!strcmp(line,"LOAD\n")){
            c->setKeys(c,0);
            puts(state_io(c,line[0]=='S')?"OK state":"ERR state");fflush(stdout);continue;
        }
        if(sscanf(line,"READ %x %u %c",&a,&n,&extra)==2){
            if(n>32768||!(range(a,n,0x02000000,0x02040000)||
                range(a,n,0x03000000,0x03008000)||
                range(a,n,0x08000000,0x08000000+(unsigned)size)))puts("ERR range");
            else{
                fputs("DATA ",stdout);
                for(unsigned i=0;i<n;++i)printf("%02x",c->busRead8(c,a+i));
                putchar('\n');
            }
        }else if(!strcmp(line,"FRAME\n")){
            /* libmGBA's standard 32-bit RGBX color_t output. */
            if(sizeof(color_t)!=4)puts("ERR pixel format");
            else{
                fputs("RGB ",stdout);
                for(unsigned j=0;j<w*h;++j){
                    uint32_t p=(uint32_t)video[j];
                    printf("%02x%02x%02x",(unsigned)(p&255),(unsigned)((p>>8)&255),(unsigned)((p>>16)&255));
                }
                putchar('\n');
            }
        }else if(sscanf(line,"STEP %x %u %c",&a,&n,&extra)==2){
            if(a>0x3ff||!n||n>600||n>200000u-frames)puts("ERR budget");
            else{
                c->setKeys(c,a);
                for(unsigned i=0;i<n&&!crashed;++i){c->runFrame(c);++frames;}
                c->setKeys(c,0);
                if(crashed)puts("ERR crash");else printf("OK %u\n",frames);
            }
        }else puts("ERR command");
        fflush(stdout);
    }
    c->setKeys(c,0);c->deinit(c);free(video);
    return crashed?5:0;
}
