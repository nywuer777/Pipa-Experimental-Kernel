package dev.pipa.framegen.lab;

import android.app.Activity;
import android.os.Bundle;
import android.graphics.Color;
import android.graphics.Typeface;
import android.view.Surface;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.util.concurrent.atomic.AtomicBoolean;

public final class PresenterActivity extends Activity implements SurfaceHolder.Callback {
    static { System.loadLibrary("pipa_lab"); }
    private native String nativePresent(Surface surface, byte[] motion, byte[] warp,
                                        byte[] scene, int targetHz, int frames, boolean continuous, boolean holdInsteadOfFG);
    private native void nativeStop();
    private final AtomicBoolean running = new AtomicBoolean(false);
    private volatile boolean validSurface = false;
    private SurfaceView surfaceView;
    private TextView status;
    private Button start60, start120, start144, stop, animate120, animate144, hold144, diagHold144, diagFg144, v2Hold144, v2Fg144;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(18, 12, 18, 14);
        root.setBackgroundColor(0xff0f0f13);
        TextView title = text("PIPA FRAMEGEN / EXP29.17 - PROCEDURAL V2", 21, Color.WHITE);
        title.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
        root.addView(title);
        root.addView(text("Vulkan FIFO 720p | textura procedural V2 sem faixas | HOLD vs FrameGen",13,0xffbbbbc2));
        status = text("Superfície não inicializada.",14,0xffeeeeee);
        root.addView(status);
        LinearLayout controls = new LinearLayout(this);
        controls.setOrientation(LinearLayout.HORIZONTAL);
        start60=button("60 Hz (solicitar)");
        start120=button("120 Hz (solicitar)");
        start144=button("144 Hz (solicitar)");
        stop=button("Parar");
        for(Button b:new Button[]{start60,start120,start144,stop}) {
            controls.addView(b,new LinearLayout.LayoutParams(0,dp(48),1));
        }
        root.addView(controls,new LinearLayout.LayoutParams(-1,dp(52)));
        LinearLayout continuousControls=new LinearLayout(this);
        continuousControls.setOrientation(LinearLayout.HORIZONTAL);
        animate120=button("2x: 60 reais + 60 gerados = 120 Hz");
        animate144=button("2x: 72 reais + 72 gerados = 144 Hz");
        continuousControls.addView(animate120,new LinearLayout.LayoutParams(0,dp(48),1));
        continuousControls.addView(animate144,new LinearLayout.LayoutParams(0,dp(48),1));
        root.addView(continuousControls,new LinearLayout.LayoutParams(-1,dp(52)));
        hold144=button("Controle 72→144: repetir original (HOLD), sem FrameGen");
        root.addView(hold144,new LinearLayout.LayoutParams(-1,dp(48)));
        LinearLayout diagnosticControls=new LinearLayout(this);
        diagnosticControls.setOrientation(LinearLayout.HORIZONTAL);
        diagHold144=button("DIAG sólido HOLD 72→144 (sem FG)");
        diagFg144=button("DIAG sólido FrameGen 72→144");
        diagnosticControls.addView(diagHold144,new LinearLayout.LayoutParams(0,dp(48),1));
        diagnosticControls.addView(diagFg144,new LinearLayout.LayoutParams(0,dp(48),1));
        root.addView(diagnosticControls,new LinearLayout.LayoutParams(-1,dp(52)));
        LinearLayout v2Controls=new LinearLayout(this);
        v2Controls.setOrientation(LinearLayout.HORIZONTAL);
        v2Hold144=button("V2 corrigida HOLD 72→144 (sem FG)");
        v2Fg144=button("V2 corrigida FrameGen 72→144");
        v2Controls.addView(v2Hold144,new LinearLayout.LayoutParams(0,dp(48),1));
        v2Controls.addView(v2Fg144,new LinearLayout.LayoutParams(0,dp(48),1));
        root.addView(v2Controls,new LinearLayout.LayoutParams(-1,dp(52)));
        surfaceView = new SurfaceView(this);
        surfaceView.getHolder().addCallback(this);
        root.addView(surfaceView,new LinearLayout.LayoutParams(-1,0,1f));
        root.addView(text("A versão V2 substitui o ruído fino e elimina a região crescente de x=0. Compare V2 HOLD e V2 FrameGen com a cena procedural antiga e DIAG sólido. Vermelho/verde são cantos superiores, azul/amarelo inferiores em coordenadas da textura. Todos os modos seguem via VkSwapchainKHR; controles anteriores mantidos. "
            +"Chamadas vkQueuePresentKHR não provam FPS exibidos; quando a extensão for suportada, os tempos reais são relatados pelo driver. "
            +"FIFO, compositor e VSync controlam a apresentação. Nenhum driver/kernel é modificado.",12,0xff9b9ba7));
        setContentView(root);
        start60.setOnClickListener(v->start(60));
        start120.setOnClickListener(v->start(120));
        start144.setOnClickListener(v->start(144));
        animate120.setOnClickListener(v->start(120,true));
        animate144.setOnClickListener(v->start(144,true));
        hold144.setOnClickListener(v->start(144,true,true));
        diagHold144.setOnClickListener(v->start(144,true,true,true));
        diagFg144.setOnClickListener(v->start(144,true,false,true));
        v2Hold144.setOnClickListener(v->start(144,true,true,false,true));
        v2Fg144.setOnClickListener(v->start(144,true,false,false,true));
        stop.setOnClickListener(v->nativeStop());
        toggle(true);
    }
    private int dp(int value) {
        return Math.round(value*getResources().getDisplayMetrics().density);
    }
    private String displayHz() {
        if(getDisplay()==null)return "indisponível";
        return String.format(java.util.Locale.US,"%.2f",getDisplay().getRefreshRate());
    }
    private TextView text(String value,int sp,int color) {
        TextView t=new TextView(this);
        t.setText(value);t.setTextSize(sp);t.setTextColor(color);
        return t;
    }
    private Button button(String label) {
        Button b=new Button(this);
        b.setText(label);b.setAllCaps(false);b.setSingleLine(true);b.setTextSize(11);
        return b;
    }
    private void toggle(boolean enabled) {
        start60.setEnabled(enabled && validSurface);
        start120.setEnabled(enabled && validSurface);
        start144.setEnabled(enabled && validSurface);
        stop.setEnabled(!enabled);
        animate120.setEnabled(enabled && validSurface);
        animate144.setEnabled(enabled && validSurface);
        hold144.setEnabled(enabled && validSurface);
        diagHold144.setEnabled(enabled && validSurface);
        diagFg144.setEnabled(enabled && validSurface);
        v2Hold144.setEnabled(enabled && validSurface);
        v2Fg144.setEnabled(enabled && validSurface);
    }
    private byte[] load(String filename) throws Exception {
        try(InputStream in=getAssets().open(filename); ByteArrayOutputStream out=new ByteArrayOutputStream()) {
            byte[] part=new byte[8192]; int n;
            while((n=in.read(part))>=0)out.write(part,0,n);
            return out.toByteArray();
        }
    }
    private void start(int hz) { start(hz,false,false,false); }
    private void start(int hz,boolean continuous) { start(hz,continuous,false,false); }
    private void start(int hz,boolean continuous,boolean holdInsteadOfFG) {
        start(hz,continuous,holdInsteadOfFG,false);
    }
    private void start(int hz,boolean continuous,boolean holdInsteadOfFG,boolean diagnostic) {
        start(hz,continuous,holdInsteadOfFG,diagnostic,false);
    }
    private void start(int hz,boolean continuous,boolean holdInsteadOfFG,boolean diagnostic,boolean v2) {
        if(!validSurface || !running.compareAndSet(false,true))return;
        toggle(false);
        status.setText((v2?"CENA V2 ":diagnostic?"CENA DIAG ":"CENA ORIGINAL ")+
              (holdInsteadOfFG?"HOLD GPU ":continuous?"2x GPU ":"A/B ")+hz+
              " Hz | tela "+displayHz()+" Hz | criando Vulkan...");
        final Surface surface=surfaceView.getHolder().getSurface();
        new Thread(()->{
            String result;
            try {
                byte[] motion=load("pipa_motion_sparse.comp.spv");
                byte[] warp=load("pipa_interpolate_tiled.comp.spv");
                byte[] scene=continuous?load(v2?"pipa_scene_v2.comp.spv":
                    diagnostic?"pipa_scene_diagnostic.comp.spv":"pipa_scene.comp.spv"):null;
                result=nativePresent(surface,motion,warp,scene,hz,240,continuous,holdInsteadOfFG);
            } catch(Throwable ex) {
                result="Falha: "+ex.getClass().getSimpleName()+": "+ex.getMessage();
            }
            final String finalResult=result+(v2?
                " | FONTE=V2 tileable sem clamp":
                diagnostic?" | FONTE=DIAGNOSTICA quadrantes solidos; sem ruido":
                " | FONTE=PROCEDURAL antiga");
            running.set(false);
            runOnUiThread(()->{
                status.setText(finalResult+"\nTela Android informa "+displayHz()+" Hz.");
                toggle(true);
            });
        },"pipa-vulkan-presenter").start();
    }
    @Override public void surfaceCreated(SurfaceHolder holder) {
        validSurface=true;
        status.setText("Superfície pronta. Selecione uma cadência de apresentação.");
        toggle(!running.get());
    }
    @Override public void surfaceChanged(SurfaceHolder h,int format,int w,int height) {
        if(w>0 && height>0) validSurface=true;
    }
    @Override public void surfaceDestroyed(SurfaceHolder holder) {
        validSurface=false;
        nativeStop();
        toggle(false);
    }
    @Override protected void onDestroy() {
        nativeStop();
        super.onDestroy();
    }
}
