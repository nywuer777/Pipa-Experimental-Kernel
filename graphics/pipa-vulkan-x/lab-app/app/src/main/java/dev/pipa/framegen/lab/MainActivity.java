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
    private Button run;
    private native int[] nativeGenerate(int[] a, int[] b, int width, int height, byte[] motion, byte[] interp);
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
        TextView title = label("PIPA FRAMEGEN  /  EXP29.4", 23, Color.WHITE);
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
        base.addView(label("Métrica: tempo de submissão e espera no CPU (inclui cópias e sincronização); não é tempo interno do shader. Saída exibida no Android UI, sem swapchain de jogo.",12,0xff9999a5));
        run.setOnClickListener(v->runTest());
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
    private Bitmap asBitmap(int[] argb) {
        Bitmap bmp=Bitmap.createBitmap(W,H,Bitmap.Config.ARGB_8888);
        bmp.setPixels(argb,0,W,0,0,W,H);
        return bmp;
    }
    private static int sample(int x,int y) {
        x=Math.max(0,Math.min(W-1,x));
        int coarse=((x/16+y/16)&1)==0?32:46;
        int texture=(x*17+y*23+(x*y)%29)&63;
        int r=Math.min(255,coarse+texture*2);
        int g=Math.min(255,coarse+texture);
        int b=Math.min(255,coarse+texture/2);
        return Color.argb(255,r,g,b);
    }
    private static int[] buildFrame(int shift) {
        int[] frame=new int[W*H];
        for(int y=0;y<H;y++)for(int x=0;x<W;x++)frame[y*W+x]=sample(x-shift,y);
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
    private static String accuracy(int[] gpu) {
        // Known ideal midpoint: frame B is frame A shifted exactly +2 px.
        long gpuError=0, naiveError=0, samples=0;
        for(int y=20;y<H-20;y++)for(int x=20;x<W-20;x++) {
            int index=y*W+x;
            int want=sample(x-1,y);
            int past=PREVIOUS[index],now=CURRENT[index];
            for(int shift:new int[]{0,8,16}) {
                int expected=(want>>>shift)&255;
                int actual=(gpu[index]>>>shift)&255;
                int naive=(((past>>>shift)&255)+((now>>>shift)&255)+1)/2;
                gpuError+=Math.abs(actual-expected);
                naiveError+=Math.abs(naive-expected);
                samples++;
            }
        }
        double maeGpu=gpuError/(double)Math.max(samples,1);
        double maeNaive=naiveError/(double)Math.max(samples,1);
        return String.format(Locale.US,
          "Erro medio vs. frame ideal: GPU=%.2f / blend simples=%.2f (menor e melhor).",
          maeGpu,maeNaive);
    }

    private void runTest() {
        run.setEnabled(false);
        status.setText("Preparando recursos Vulkan e executando shader...");
        new Thread(()->{
            try {
                byte[] motion=shader("pipa_motion.comp.spv");
                byte[] interp=shader("pipa_interpolate.comp.spv");
                long start=SystemClock.elapsedRealtimeNanos();
                int[] pixels=nativeGenerate(PREVIOUS,CURRENT,W,H,motion,interp);
                double totalMs=(SystemClock.elapsedRealtimeNanos()-start)/1000000.0;
                String report=nativeReport();
                final String score=pixels!=null && pixels.length==W*H ? accuracy(pixels) : "";
                runOnUiThread(()->{
                    if(pixels!=null && pixels.length==W*H) {
                        result.setImageBitmap(asBitmap(pixels));
                        status.setText("GPU: execução concluída. "+report+
                            "\nTempo total JNI+Vulkan: "+String.format(Locale.US,"%.2f ms",totalMs)+
                            ". "+score+" Não implica ganho de FPS na apresentação.");
                    } else {
                        status.setText("Falha no teste: "+report);
                    }
                    run.setEnabled(true);
                });
            } catch (Throwable t) {
                runOnUiThread(()->{
                    status.setText("Falha: "+t.getClass().getSimpleName()+": "+t.getMessage());
                    run.setEnabled(true);
                });
            }
        },"pipa-vk-lab").start();
    }
}
