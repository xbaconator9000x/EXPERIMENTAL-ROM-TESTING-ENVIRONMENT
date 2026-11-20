/* Read-only state assertions and real controller input through libmGBA. */
#include <mgba/core/core.h>
#include <mgba/core/interface.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#ifdef _WIN32
#include <direct.h>
#define create_dir(path) _mkdir(path)
#else
#include <sys/stat.h>
#define create_dir(path) mkdir(path,0700)
#endif
#define STRIDE 256
#define CAP 200000u
static volatile int crashed;
static unsigned frame, checks;
static void on_crash(void *p) { (void)p; crashed=1; }
static int key(const char *s) {
    const char *names[]={"A","B","SELECT","START","RIGHT","LEFT","UP","DOWN","R","L"};
    for(int i=0;i<10;i++) if(!strcmp(s,names[i])) return 1<<i;
    return -1;
}
static int number(const char *s, uint32_t *out) {
    char *end; unsigned long long n;
    if(!*s || *s=='-') return 0;
    errno=0; n=strtoull(s,&end,0);
    if(errno || *end || n>UINT32_MAX) return 0;
    *out=(uint32_t)n; return 1;
}
static int step(struct mCore *c, unsigned keys) {
    if(crashed || frame>=CAP) return 0;
    c->setKeys(c,keys); c->runFrame(c); ++frame;
    return !crashed;
}
static int valid_addr(uint32_t w,uint32_t a) {
    if(w!=8 && w!=16 && w!=32) return 0;
    unsigned n=w/8;
    if(a%n) return 0;
    return (a>=0x02000000u && a<=0x02040000u-n) ||
           (a>=0x03000000u && a<=0x03008000u-n) ||
           (a>=0x06000000u && a<=0x06018000u-n);
}
static uint32_t read_value(struct mCore *c,uint32_t w,uint32_t a) {
    return w==8?c->busRead8(c,a):w==16?c->busRead16(c,a):c->busRead32(c,a);
}
static int capture(const char *dir,const uint32_t *pixels,unsigned line) {
    char target[4096]; int length=snprintf(target,sizeof(target),"%s/frame_%06u_line_%u.ppm",dir,frame,line);
    if(length<0 || (size_t)length>=sizeof(target)) return 0;
    FILE *out=fopen(target,"wb"); if(!out) return 0;
    int ok=fprintf(out,"P6\n240 160\n255\n")>0;
    for(int y=0;y<160;y++) for(int x=0;x<240;x++) {
        uint32_t p=pixels[y*STRIDE+x]; unsigned char rgb[]={p&255,(p>>8)&255,(p>>16)&255};
        if(fwrite(rgb,1,3,out)!=3) ok=0;
    }
    return fclose(out)==0 && ok;
}
int main(int argc,char **argv) {
    if(argc!=4){fprintf(stderr,"usage: %s ROM scenario outdir\n",argv[0]);return 2;}
    FILE *in=fopen(argv[2],"r"); if(!in){perror("scenario");return 2;}
    if(create_dir(argv[3])&&errno!=EEXIST){perror("output");fclose(in);return 2;}
    struct mCore *c=mCoreFind(argv[1]);
    if(!c || !c->init(c)){fclose(in);return 3;}
    mCoreInitConfig(c,"gba-state-runner");
    uint32_t *pixels=calloc(STRIDE*160,sizeof(*pixels));
    if(!pixels){c->deinit(c);fclose(in);return 3;}
    c->setVideoBuffer(c,pixels,STRIDE);
    struct mCoreCallbacks cb={0}; cb.coreCrashed=on_crash; c->addCoreCallbacks(c,&cb);
    if(!mCoreLoadFile(c,argv[1])) { free(pixels);c->deinit(c);fclose(in);return 4;}
    c->reset(c);
    char buf[512]; unsigned line=0; int status=0;
    while(!status && fgets(buf,sizeof(buf),in)){
        ++line;
        if(!strchr(buf,'\n') && !feof(in)){status=2;break;}
        char *comment=strchr(buf,'#'); if(comment)*comment=0;
        char *v[8]; unsigned n=0;
        char *tok=strtok(buf," \t\r\n");
        while(tok && n<8){v[n++]=tok;tok=strtok(NULL," \t\r\n");}
        if(!n)continue;
        if(tok){status=2;break;}
        if(!strcmp(v[0],"idle") || !strcmp(v[0],"press")){
            int press=!strcmp(v[0],"press"), k=press&&n==3?key(v[1]):0;
            uint32_t count;
            if(n!=(unsigned)(press?3:2)||k<0||!number(v[n-1],&count)||!count||count>CAP-frame){status=2;break;}
            printf("INPUT line=%u frame=%u keys=%d duration=%u\n",line,frame,k,count);
            for(uint32_t i=0;i<count;i++) if(!step(c,k)){status=5;break;}
            c->setKeys(c,0);
        } else if(!strcmp(v[0],"assert") || !strcmp(v[0],"wait")){
            int wait=!strcmp(v[0],"wait");
            uint32_t w,a,mask,expected,limit=0;
            if(n!=(unsigned)(wait?6:5)||!number(v[1],&w)||!number(v[2],&a)||
               !number(v[3],&mask)||!number(v[4],&expected)||!valid_addr(w,a)||
               !mask||(w<32 && (mask>>w))||(expected&~mask)||
               (wait && (!number(v[5],&limit)||!limit||limit>CAP-frame))){status=2;break;}
            uint32_t actual=read_value(c,w,a);
            while(!crashed && (actual&mask)!=expected && limit){
                --limit;
                if(!step(c,0)){status=5;break;}
                actual=read_value(c,w,a);
            }
            if(!status && ((actual&mask)!=expected || crashed)) status=5;
            printf("%s line=%u frame=%u addr=%08x actual=%08x mask=%08x expected=%08x\n",
                   status?"FAIL":"PASS",line,frame,a,actual,mask,expected);
            if(!status)++checks;
        } else if(!strcmp(v[0],"capture") && n==1){
            if(!capture(argv[3],pixels,line)) status=4;
        } else status=2;
    }
    if(ferror(in))status=4;
    if(crashed)status=5;
    if(!status&&!checks)status=2;
    printf("RESULT %s frame=%u checks=%u line=%u core_crash=%d\n",status?"FAIL":"PASS",frame,checks,line,crashed);
    if(status)capture(argv[3],pixels,line);
    fclose(in);c->setKeys(c,0);c->unloadROM(c);c->deinit(c);free(pixels);
    return status;
}
