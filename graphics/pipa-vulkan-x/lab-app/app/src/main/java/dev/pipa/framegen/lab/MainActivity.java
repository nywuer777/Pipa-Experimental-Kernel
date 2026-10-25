package dev.pipa.framegen.lab;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.View;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.Locale;

public final class MainActivity extends Activity {
    private static final int W = 256, H = 128;
    private static final int BG = Color.rgb(15, 15, 19);
    private static final int[] PREVIOUS = buildFrame(0);
    private static final int[] CURRENT = buildFrame(2);
    static { System.loadLibrary("pipa_lab"); }

    private TextView status;
    private ImageView result;
    private Button run, benchmark, fastButton, largeButton, parallelSmall, parallelLarge;
    private Button sparseLarge, parallel720, sparse720;
    private Button adaptive360, adaptive720;
    private Button sparse32Adaptive720, tiled360, tiled720, sparse32Tiled720;
    private native int[] nativeGenerate(int[] a, int[] b, int width, int height, byte[] motion, byte[] interp, int repetitions, int motionVariant, boolean tiledWarp);
    private native String nativeReport();

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        ScrollView outer = new ScrollView(this);
        outer.setFillViewport(true);
        outer.setBackgroundColor(BG);
        LinearLayout base = new LinearLayout(this);
        base.setOrientation(LinearLayout.VERTICAL);
        base.setPadding(dp(24),dp(14),dp(24),dp(22));
        outer.addView(base);
        TextView title = label("PIPA FRAMEGEN  /  EXP29.13", 23, Color.WHITE);
        title.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
        base.addView(title);
        base.addView(label("Vulkan Compute • teste offscreen • Adreno 650 / Android ARM64",13,0xffaaaaaf));
        status=label("Pronto para testar. Nenhuma alteração no driver ou no kernel.",14,0xffd3d3d7);
        status.setPadding(0,dp(12),0,dp(12));
        base.addView(status);
        run=new Button(this);
        run.setAllCaps(false);
        run.setText("Executar interpolação na GPU");
        benchmark=new Button(this);
        benchmark.setAllCaps(false);
        benchmark.setText("Benchmark GPU (1 aquecimento + 32 amostras)");
        fastButton=new Button(this);
        fastButton.setAllCaps(false);
        fastButton.setText("Benchmark FAST 256×128 (32 amostras)");
        largeButton=new Button(this);
        largeButton.setAllCaps(false);
        largeButton.setText("Benchmark FAST 640×360 (8 amostras)");
        parallelSmall=new Button(this);
        parallelSmall.setAllCaps(false);
        parallelSmall.setText("Benchmark PARALLEL 256×128 (32 amostras)");
        parallelLarge=new Button(this);
        parallelLarge.setAllCaps(false);
        parallelLarge.setText("Benchmark PARALLEL 640×360 (8 amostras)");
        sparseLarge=new Button(this);
        sparseLarge.setAllCaps(false);
        sparseLarge.setText("Benchmark SPARSE 640×360 (8 amostras)");
        parallel720=new Button(this);
        parallel720.setAllCaps(false);
        parallel720.setText("Benchmark PARALLEL 1280×720 (8 amostras)");
        sparse720=new Button(this);
        sparse720.setAllCaps(false);
        sparse720.setText("SPARSE FIX 1280×720 (8)");
        run.setText("Interpolar");
        benchmark.setText("LEGACY 256×128 (32)");
        fastButton.setText("FAST 256×128 (32)");
        parallelSmall.setText("PARALLEL 256×128 (32)");
        largeButton.setText("FAST 640×360 (8)");
        parallelLarge.setText("PARALLEL 640×360 (8)");
        sparseLarge.setText("SPARSE FIX 640×360 (8)");
        parallel720.setText("PARALLEL 1280×720 (8)");
        controlRow(base,run,benchmark);
        controlRow(base,fastButton,parallelSmall);
        controlRow(base,largeButton,parallelLarge,sparseLarge);
        controlRow(base,parallel720,sparse720);
        adaptive360=new Button(this);
        adaptive360.setAllCaps(false);
        adaptive360.setText("SPARSE+ADAPTIVE 640×360 (8)");
        adaptive720=new Button(this);
        adaptive720.setAllCaps(false);
        adaptive720.setText("SPARSE+ADAPTIVE 1280×720 (8)");
        controlRow(base,adaptive360,adaptive720);
        sparse32Adaptive720=new Button(this);
        sparse32Adaptive720.setAllCaps(false);
        sparse32Adaptive720.setText("SPARSE32+ADAPTIVE 720p");
        tiled360=new Button(this);
        tiled360.setAllCaps(false);
        tiled360.setText("SPARSE+TILED 360p");
        tiled720=new Button(this);
        tiled720.setAllCaps(false);
        tiled720.setText("SPARSE+TILED 720p");
        sparse32Tiled720=new Button(this);
        sparse32Tiled720.setAllCaps(false);
        sparse32Tiled720.setText("SPARSE32+TILED 720p");
        controlRow(base,sparse32Adaptive720,tiled360);
        controlRow(base,tiled720,sparse32Tiled720);
        Button presenterButton=new Button(this);
        presenterButton.setText("Abrir Vulkan Presenter — Frames reais + gerados");
        presenterButton.setTextSize(12);
        presenterButton.setAllCaps(false);
        base.addView(presenterButton,new LinearLayout.LayoutParams(-1,dp(46)));
        presenterButton.setOnClickListener(v->
            startActivity(new Intent(this,PresenterActivity.class)));
        LinearLayout pictures=new LinearLayout(this);
        pictures.setOrientation(LinearLayout.HORIZONTAL);
        pictures.setPadding(0,dp(12),0,0);
        base.addView(pictures);
        picture(pictures,"Frame real A",PREVIOUS);
        picture(pictures,"Frame real B",CURRENT);
        LinearLayout generated=new LinearLayout(this);
        generated.setOrientation(LinearLayout.VERTICAL);
        generated.setPadding(0,dp(12),0,0);
        base.addView(generated);
        generated.addView(label("Frame intermediário (GPU)",14,0xffeeeeee));
        result=new ImageView(this);
        result.setAdjustViewBounds(true);
        result.setScaleType(ImageView.ScaleType.FIT_CENTER);
        result.setBackgroundColor(0xff242428);
        generated.addView(result,new LinearLayout.LayoutParams(-1,dp(160)));
        base.addView(label("GPU: Motion / Warp / Total. EXP29.11 testa SPARSE32 e TILED contra SPARSE+ADAPTIVE. Offscreen, sem FPS físicos; qualidade sintética não representa jogos.",12,0xff9999a5));
        run.setOnClickListener(v->runTest(1,0,256,128));
        benchmark.setOnClickListener(v->runTest(33,0,256,128));
        fastButton.setOnClickListener(v->runTest(33,1,256,128));
        largeButton.setOnClickListener(v->runTest(9,1,640,360));
        parallelSmall.setOnClickListener(v->runTest(33,2,256,128));
        parallelLarge.setOnClickListener(v->runTest(9,2,640,360));
        sparseLarge.setOnClickListener(v->runTest(9,3,640,360));
        parallel720.setOnClickListener(v->runTest(9,2,1280,720));
        sparse720.setOnClickListener(v->runTest(9,3,1280,720));
        adaptive360.setOnClickListener(v->runTest(9,3,640,360,true));
        adaptive720.setOnClickListener(v->runTest(9,3,1280,720,true));
        sparse32Adaptive720.setOnClickListener(v->runTest(9,4,1280,720,true,false));
        tiled360.setOnClickListener(v->runTest(9,3,640,360,true,true));
        tiled720.setOnClickListener(v->runTest(9,3,1280,720,true,true));
        sparse32Tiled720.setOnClickListener(v->runTest(9,4,1280,720,true,true));
        setContentView(outer);
    }

    private void controlRow(LinearLayout parent, Button... items) {
        LinearLayout line=new LinearLayout(this);
        line.setOrientation(LinearLayout.HORIZONTAL);
        parent.addView(line,new LinearLayout.LayoutParams(-1,dp(48)));
        for(Button item:items) {
            item.setTextSize(12);
            item.setSingleLine(true);
            LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,dp(46),1f);
            lp.setMargins(dp(2),0,dp(2),0);
            line.addView(item,lp);
        }
    }

    private void picture(LinearLayout parent,String name,int[] data) {
        LinearLayout column=new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);
        LinearLayout.LayoutParams c=new LinearLayout.LayoutParams(0,-2,1f);
        c.setMargins(0,0,dp(8),0);
        parent.addView(column,c);
        column.addView(label(name,13,Color.WHITE));
        ImageView image=new ImageView(this);
        image.setAdjustViewBounds(true);
        image.setScaleType(ImageView.ScaleType.FIT_CENTER);
        image.setImageBitmap(asBitmap(data));
        column.addView(image,new LinearLayout.LayoutParams(-1,dp(105)));
    }
    private Bitmap asBitmap(int[] argb) { return asBitmap(argb,W,H); }
    private Bitmap asBitmap(int[] argb,int width,int height) {
        Bitmap bmp=Bitmap.createBitmap(width,height,Bitmap.Config.ARGB_8888);
        bmp.setPixels(argb,0,width,0,0,width,height);
        return bmp;
    }
    private static int sample(int x,int y,int width,int height) {
        x=Math.max(0,Math.min(width-1,x));
        y=Math.max(0,Math.min(height-1,y));
        int coarse=((x/16+y/16)&1)==0?32:46;
        int texture=(x*17+y*23+(x*y)%29)&63;
        int r=Math.min(255,coarse+texture*2);
        int g=Math.min(255,coarse+texture);
        int b=Math.min(255,coarse+texture/2);
        return Color.argb(255,r,g,b);
    }
    private static int sample(int x,int y) { return sample(x,y,W,H); }
    private static int[] buildFrame(int shift) { return buildFrame(shift,W,H); }
    private static int[] buildFrame(int shift,int width,int height) {
        int[] frame=new int[width*height];
        for(int y=0;y<height;y++)for(int x=0;x<width;x++)
            frame[y*width+x]=sample(x-shift,y,width,height);
        return frame;
    }
    private static int dp(float dp) { return (int)(dp*android.content.res.Resources.getSystem().getDisplayMetrics().density+0.5f); }
    private TextView label(String value,int sp,int color) {
        TextView t=new TextView(this);
        t.setText(value);
        t.setTextSize(sp);
        t.setTextColor(color);
        return t;
    }
    private byte[] shader(String name) throws IOException {
        try(InputStream in=getAssets().open(name); ByteArrayOutputStream out=new ByteArrayOutputStream()) {
            byte[] chunk=new byte[8192]; int n;
            while((n=in.read(chunk))!=-1)out.write(chunk,0,n);
            return out.toByteArray();
        }
    }
    private static String accuracy(int[] gpu,int[] previous,int[] current,
                                   int width,int height) {
        long gpuError=0,naiveError=0,samples=0;
        for(int y=20;y<height-20;y++)for(int x=20;x<width-20;x++) {
            int i=y*width+x, want=sample(x-1,y,width,height);
            for(int shift:new int[]{0,8,16}) {
                int expected=(want>>>shift)&255;
                int actual=(gpu[i]>>>shift)&255;
                int naive=(((previous[i]>>>shift)&255)+
                           ((current[i]>>>shift)&255)+1)/2;
                gpuError+=Math.abs(actual-expected);
                naiveError+=Math.abs(naive-expected);
                samples++;
            }
        }
        return String.format(Locale.US,
            (gpuError <= samples ? "QUALIDADE OK | " : "QUALIDADE FALHOU | ") + "MAE: GPU=%.2f / blend=%.2f (menor melhor)",
            gpuError/(double)Math.max(samples,1),
            naiveError/(double)Math.max(samples,1));
    }
    private void enableControls(boolean enabled) {
        run.setEnabled(enabled); benchmark.setEnabled(enabled);
        fastButton.setEnabled(enabled); largeButton.setEnabled(enabled);
        parallelSmall.setEnabled(enabled); parallelLarge.setEnabled(enabled);
        sparseLarge.setEnabled(enabled); parallel720.setEnabled(enabled);
        sparse720.setEnabled(enabled);
        adaptive360.setEnabled(enabled); adaptive720.setEnabled(enabled);
        sparse32Adaptive720.setEnabled(enabled); tiled360.setEnabled(enabled);
        tiled720.setEnabled(enabled); sparse32Tiled720.setEnabled(enabled);
    }

    private void runTest(int repetitions,int motionVariant,int width,int height) {
        runTest(repetitions,motionVariant,width,height,false);
    }
    private void runTest(int repetitions,int motionVariant,int width,int height,
                         boolean adaptiveWarp) {
        runTest(repetitions,motionVariant,width,height,adaptiveWarp,false);
    }
    private void runTest(int repetitions,int motionVariant,int width,int height,
                         boolean adaptiveWarp,boolean tiledWarp) {
        enableControls(false);
        final String label=(motionVariant==4?"SPARSE32":motionVariant==3?"SPARSE":motionVariant==2?"PARALLEL":motionVariant==1?"FAST":"LEGACY")+
            (tiledWarp?"+TILED":adaptiveWarp?"+ADAPTIVE":"")+" "+width+"×"+height;
        status.setText("GPU: preparando "+label+" ("+repetitions+" passagens)...");
        new Thread(()->{
            try {
                byte[] motion=shader(motionVariant==4?"pipa_motion_sparse32.comp.spv":
                    motionVariant==3?"pipa_motion_sparse.comp.spv":
                    motionVariant==2?"pipa_motion_parallel.comp.spv":
                    motionVariant==1?"pipa_motion_fast.comp.spv":"pipa_motion.comp.spv");
                byte[] interp=shader(tiledWarp?"pipa_interpolate_tiled.comp.spv":
                    adaptiveWarp?"pipa_interpolate_adaptive.comp.spv":"pipa_interpolate.comp.spv");
                int[] previous=width==W && height==H ?
                    PREVIOUS : buildFrame(0,width,height);
                int[] current=width==W && height==H ?
                    CURRENT : buildFrame(2,width,height);
                long start=SystemClock.elapsedRealtimeNanos();
                int[] pixels=nativeGenerate(previous,current,width,height,
                                            motion,interp,repetitions,motionVariant,tiledWarp);
                double totalMs=(SystemClock.elapsedRealtimeNanos()-start)/1000000.0;
                String report=nativeReport();
                final String quality=pixels!=null && pixels.length==width*height ?
                      accuracy(pixels,previous,current,width,height) : "";
                runOnUiThread(()->{
                    if(pixels!=null && pixels.length==width*height) {
                        result.setImageBitmap(asBitmap(pixels,width,height));
                        status.setText(label+" — GPU: execução concluída\n"+report+
                            "\nJNI + Vulkan total: "+String.format(Locale.US,"%.2f ms",totalMs)+
                            "\n"+quality+
                            "\nSem swapchain e sem medição de FPS apresentados.");
                    } else {
                        status.setText(label+" — falha no teste: "+report);
                    }
                    enableControls(true);
                });
            } catch(Throwable t) {
                runOnUiThread(()->{
                    status.setText(label+" — falha: "+t.getClass().getSimpleName()+
                                   ": "+t.getMessage());
                    enableControls(true);
                });
            }
        },"pipa-framegen-benchmark").start();
    }

}
