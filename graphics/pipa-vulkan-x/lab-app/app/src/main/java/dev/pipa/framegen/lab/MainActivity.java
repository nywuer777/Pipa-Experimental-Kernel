package dev.pipa.framegen.lab;

import android.app.Activity;
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
    private native int[] nativeGenerate(int[] a, int[] b, int width, int height, byte[] motion, byte[] interp, int repetitions, int motionVariant);
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
        TextView title = label("PIPA FRAMEGEN  /  EXP29.7", 23, Color.WHITE);
        title.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
        base.addView(title);
        base.addView(label("Vulkan Compute • teste offscreen • Adreno 650 / Android ARM64",13,0xffaaaaaf));
        status=label("Pronto para testar. Nenhuma alteração no driver ou no kernel.",14,0xffd3d3d7);
        status.setPadding(0,dp(12),0,dp(12));
        base.addView(status);
        run=new Button(this);
        run.setAllCaps(false);
        run.setText("Executar interpolação na GPU");
        base.addView(run,new LinearLayout.LayoutParams(-1,dp(52)));
        benchmark=new Button(this);
        benchmark.setAllCaps(false);
        benchmark.setText("Benchmark GPU (1 aquecimento + 32 amostras)");
        base.addView(benchmark,new LinearLayout.LayoutParams(-1,dp(52)));
        fastButton=new Button(this);
        fastButton.setAllCaps(false);
        fastButton.setText("Benchmark FAST 256×128 (32 amostras)");
        base.addView(fastButton,new LinearLayout.LayoutParams(-1,dp(52)));
        largeButton=new Button(this);
        largeButton.setAllCaps(false);
        largeButton.setText("Benchmark FAST 640×360 (8 amostras)");
        base.addView(largeButton,new LinearLayout.LayoutParams(-1,dp(52)));
        parallelSmall=new Button(this);
        parallelSmall.setAllCaps(false);
        parallelSmall.setText("Benchmark PARALLEL 256×128 (32 amostras)");
        base.addView(parallelSmall,new LinearLayout.LayoutParams(-1,dp(52)));
        parallelLarge=new Button(this);
        parallelLarge.setAllCaps(false);
        parallelLarge.setText("Benchmark PARALLEL 640×360 (8 amostras)");
        base.addView(parallelLarge,new LinearLayout.LayoutParams(-1,dp(52)));
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
        base.addView(label("GPU: timestamps individuais de Motion, Warp+barreira e total. Comparação legado vs FAST; medições offscreen, não FPS físicos. Os painéis A/B exibem a referência 256×128.",12,0xff9999a5));
        run.setOnClickListener(v->runTest(1,0,256,128));
        benchmark.setOnClickListener(v->runTest(33,0,256,128));
        fastButton.setOnClickListener(v->runTest(33,1,256,128));
        largeButton.setOnClickListener(v->runTest(9,1,640,360));
        parallelSmall.setOnClickListener(v->runTest(33,2,256,128));
        parallelLarge.setOnClickListener(v->runTest(9,2,640,360));
        setContentView(outer);
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
            "MAE: GPU=%.2f / blend=%.2f (menor melhor)",
            gpuError/(double)Math.max(samples,1),
            naiveError/(double)Math.max(samples,1));
    }
    private void enableControls(boolean enabled) {
        run.setEnabled(enabled); benchmark.setEnabled(enabled);
        fastButton.setEnabled(enabled); largeButton.setEnabled(enabled);
        parallelSmall.setEnabled(enabled); parallelLarge.setEnabled(enabled);
    }

    private void runTest(int repetitions,int motionVariant,int width,int height) {
        enableControls(false);
        final String label=(motionVariant==2?"PARALLEL":motionVariant==1?"FAST":"LEGACY")+
            " "+width+"×"+height;
        status.setText("GPU: preparando "+label+" ("+repetitions+" passagens)...");
        new Thread(()->{
            try {
                byte[] motion=shader(motionVariant==2?"pipa_motion_parallel.comp.spv":
                    motionVariant==1?"pipa_motion_fast.comp.spv":"pipa_motion.comp.spv");
                byte[] interp=shader("pipa_interpolate.comp.spv");
                int[] previous=width==W && height==H ?
                    PREVIOUS : buildFrame(0,width,height);
                int[] current=width==W && height==H ?
                    CURRENT : buildFrame(2,width,height);
                long start=SystemClock.elapsedRealtimeNanos();
                int[] pixels=nativeGenerate(previous,current,width,height,
                                            motion,interp,repetitions,motionVariant);
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
