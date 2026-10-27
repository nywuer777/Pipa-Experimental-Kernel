package dev.pipa.framegen.lab;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.os.Bundle;
import android.os.PowerManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.view.Surface;
import android.view.View;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

public final class PresenterActivity extends Activity implements SurfaceHolder.Callback {
    static { System.loadLibrary("pipa_lab"); }
    private native String nativePresent(Surface surface, byte[] motion, byte[] warp,
                                        byte[] scene, int targetHz, int frames, boolean continuous, boolean holdInsteadOfFG,
                                        boolean alignWithDisplay, int motionRadius, boolean fit3dAspect,
                                        boolean preferIdentity3d, boolean gpuBudgetGuard);
    private native void nativeStop();
    private final AtomicBoolean running = new AtomicBoolean(false);
    private final AtomicInteger peakThermalStatus = new AtomicInteger(PowerManager.THERMAL_STATUS_NONE);
    private PowerManager powerManager;
    private final PowerManager.OnThermalStatusChangedListener thermalStatusListener =
        value -> peakThermalStatus.accumulateAndGet(value, Math::max);
    private volatile boolean validSurface = false;
    private SurfaceView surfaceView;
    private CheckBox syncDisplay, fastMotion, identity3d, gpuBudgetGuard;
    private Button copyReport;
    private TextView status;
    private Button start60, start120, start144, stop, animate120, animate144, hold144, diagHold144, diagFg144, v2Hold144, v2Fg144, stressHold144, stressFg144, scene3dHold, scene3dFg, scene3dHold60, scene3dFg60;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(18, 12, 18, 14);
        root.setBackgroundColor(0xff0f0f13);
        TextView title = text("PIPA FRAMEGEN / EXP29.45 - PIXEL READBACK", 21, Color.WHITE);
        title.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
        root.addView(title);
        root.addView(text("Vulkan FIFO 720p | WSI SYNC | testes 3D de 10s e 60s",13,0xffbbbbc2));
        status = text("Superfície não inicializada.",12,0xffeeeeee);
        root.addView(status);
        LinearLayout legacyControls=new LinearLayout(this);
        legacyControls.setOrientation(LinearLayout.VERTICAL);
        legacyControls.setVisibility(View.GONE);
        Button legacyToggle=button("Mostrar / ocultar testes anteriores");
        root.addView(legacyToggle,new LinearLayout.LayoutParams(-1,dp(38)));
        root.addView(legacyControls);
        legacyToggle.setOnClickListener(v->legacyControls.setVisibility(
            legacyControls.getVisibility()==View.GONE?View.VISIBLE:View.GONE));
        LinearLayout controls = new LinearLayout(this);
        controls.setOrientation(LinearLayout.HORIZONTAL);
        start60=button("60 Hz (solicitar)");
        start120=button("120 Hz (solicitar)");
        start144=button("144 Hz (solicitar)");
        stop=button("Parar");
        for(Button b:new Button[]{start60,start120,start144,stop}) {
            controls.addView(b,new LinearLayout.LayoutParams(0,dp(48),1));
        }
        legacyControls.addView(controls,new LinearLayout.LayoutParams(-1,dp(52)));
        LinearLayout continuousControls=new LinearLayout(this);
        continuousControls.setOrientation(LinearLayout.HORIZONTAL);
        animate120=button("2x: 60 reais + 60 gerados = 120 Hz");
        animate144=button("2x: 72 reais + 72 gerados = 144 Hz");
        continuousControls.addView(animate120,new LinearLayout.LayoutParams(0,dp(48),1));
        continuousControls.addView(animate144,new LinearLayout.LayoutParams(0,dp(48),1));
        legacyControls.addView(continuousControls,new LinearLayout.LayoutParams(-1,dp(52)));
        hold144=button("Controle 72→144: repetir original (HOLD), sem FrameGen");
        legacyControls.addView(hold144,new LinearLayout.LayoutParams(-1,dp(48)));
        LinearLayout diagnosticControls=new LinearLayout(this);
        diagnosticControls.setOrientation(LinearLayout.HORIZONTAL);
        diagHold144=button("DIAG sólido HOLD 72→144 (sem FG)");
        diagFg144=button("DIAG sólido FrameGen 72→144");
        diagnosticControls.addView(diagHold144,new LinearLayout.LayoutParams(0,dp(48),1));
        diagnosticControls.addView(diagFg144,new LinearLayout.LayoutParams(0,dp(48),1));
        legacyControls.addView(diagnosticControls,new LinearLayout.LayoutParams(-1,dp(52)));
        LinearLayout v2Controls=new LinearLayout(this);
        v2Controls.setOrientation(LinearLayout.HORIZONTAL);
        v2Hold144=button("V2 corrigida HOLD 72→144 (sem FG)");
        v2Fg144=button("V2 corrigida FrameGen 72→144");
        v2Controls.addView(v2Hold144,new LinearLayout.LayoutParams(0,dp(48),1));
        v2Controls.addView(v2Fg144,new LinearLayout.LayoutParams(0,dp(48),1));
        legacyControls.addView(v2Controls,new LinearLayout.LayoutParams(-1,dp(52)));
        LinearLayout stressControls=new LinearLayout(this);
        stressControls.setOrientation(LinearLayout.HORIZONTAL);
        stressHold144=button("STRESS 10s: V2 HOLD 72→144");
        stressFg144=button("STRESS 10s: V2 FrameGen 72→144");
        stressControls.addView(stressHold144,new LinearLayout.LayoutParams(0,dp(48),1));
        stressControls.addView(stressFg144,new LinearLayout.LayoutParams(0,dp(48),1));
        root.addView(stressControls,new LinearLayout.LayoutParams(-1,dp(52)));
        LinearLayout scene3dControls=new LinearLayout(this);
        scene3dControls.setOrientation(LinearLayout.HORIZONTAL);
        scene3dHold=button("3D 10s HOLD 72→144");
        scene3dFg=button("3D 10s FrameGen 72→144");
        scene3dControls.addView(scene3dHold,new LinearLayout.LayoutParams(0,dp(48),1));
        scene3dControls.addView(scene3dFg,new LinearLayout.LayoutParams(0,dp(48),1));
        root.addView(scene3dControls,new LinearLayout.LayoutParams(-1,dp(52)));
        LinearLayout scene3dLongControls=new LinearLayout(this);
        scene3dLongControls.setOrientation(LinearLayout.HORIZONTAL);
        scene3dHold60=button("3D 60s HOLD 72→144");
        scene3dFg60=button("3D 60s FrameGen 72→144");
        scene3dLongControls.addView(scene3dHold60,new LinearLayout.LayoutParams(0,dp(48),1));
        scene3dLongControls.addView(scene3dFg60,new LinearLayout.LayoutParams(0,dp(48),1));
        root.addView(scene3dLongControls,new LinearLayout.LayoutParams(-1,dp(52)));
        syncDisplay=new CheckBox(this);
        syncDisplay.setText("SYNC experimental: usar periodo Vulkan WSI do monitor (144 Hz)");
        syncDisplay.setTextColor(0xffdde4ee);
        syncDisplay.setTextSize(12);
        syncDisplay.setChecked(true); // EXP29.30: prefer the measured WSI period at 144 Hz.
        LinearLayout timingControls=new LinearLayout(this);
        timingControls.setOrientation(LinearLayout.HORIZONTAL);
        timingControls.addView(syncDisplay,new LinearLayout.LayoutParams(0,dp(44),3));
        copyReport=button("Copiar relatório");
        timingControls.addView(copyReport,new LinearLayout.LayoutParams(0,dp(44),1));
        root.addView(timingControls,new LinearLayout.LayoutParams(-1,dp(48)));
        fastMotion=new CheckBox(this);
        fastMotion.setText("Motion FAST experimental: raio 3 (padrao 4)");
        fastMotion.setTextColor(0xffdde4ee);
        fastMotion.setTextSize(12);
        fastMotion.setChecked(false);
        identity3d=new CheckBox(this);
        identity3d.setText("3D IDENTITY WSI (teste principal)");
        identity3d.setTextColor(0xffdde4ee);
        identity3d.setTextSize(12);
        identity3d.setChecked(true);
        LinearLayout orientationControls=new LinearLayout(this);
        orientationControls.setOrientation(LinearLayout.HORIZONTAL);
        orientationControls.addView(fastMotion,new LinearLayout.LayoutParams(0,dp(44),1));
        orientationControls.addView(identity3d,new LinearLayout.LayoutParams(0,dp(44),1));
        root.addView(orientationControls,new LinearLayout.LayoutParams(-1,dp(44)));
        gpuBudgetGuard=new CheckBox(this);
        gpuBudgetGuard.setText("GPU GUARD PAR 85%: HOLD apos 3 pares GPU acima do teto");
        gpuBudgetGuard.setTextColor(0xffdde4ee);
        gpuBudgetGuard.setTextSize(12);
        gpuBudgetGuard.setChecked(false);
        root.addView(gpuBudgetGuard,new LinearLayout.LayoutParams(-1,dp(42)));
        surfaceView = new SurfaceView(this);
        surfaceView.getHolder().addCallback(this);
        root.addView(surfaceView,new LinearLayout.LayoutParams(-1,0,1f));
        root.addView(text("EXP29.45: lê uma região 64x64 de um único frame da swapchain própria e registra um hash. O teste não captura jogos externos nem injeta quadros.",12,0xff9b9ba7));
        setContentView(root);
        powerManager=(PowerManager)getSystemService(Context.POWER_SERVICE);
        if(powerManager!=null)powerManager.addThermalStatusListener(thermalStatusListener);
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
        stressHold144.setOnClickListener(v->start(144,true,true,false,true,true));
        stressFg144.setOnClickListener(v->start(144,true,false,false,true,true));
        scene3dHold.setOnClickListener(v->start(144,true,true,false,false,true,true));
        scene3dFg.setOnClickListener(v->start(144,true,false,false,false,true,true));
        scene3dHold.setOnLongClickListener(v->{start(144,true,true,false,false,true,true,8640);return true;});
        scene3dFg.setOnLongClickListener(v->{start(144,true,false,false,false,true,true,8640);return true;});
        scene3dHold60.setOnClickListener(v->start(144,true,true,false,false,true,true,8640));
        scene3dFg60.setOnClickListener(v->start(144,true,false,false,false,true,true,8640));
        stop.setOnClickListener(v->nativeStop());
        copyReport.setOnClickListener(v->{
            ClipboardManager clipboard=(ClipboardManager)getSystemService(Context.CLIPBOARD_SERVICE);
            if(clipboard!=null)clipboard.setPrimaryClip(ClipData.newPlainText(
                "Pipa EXP29.32 diagnóstico",readDiagnostic()));
        });
        toggle(true);
    }
    private int dp(int value) {
        return Math.round(value*getResources().getDisplayMetrics().density);
    }
    private String displayHz() {
        if(getDisplay()==null)return "indisponível";
        return String.format(java.util.Locale.US,"%.2f",getDisplay().getRefreshRate());
    }
    private int currentThermalStatus() {
        return powerManager==null?PowerManager.THERMAL_STATUS_NONE:
               powerManager.getCurrentThermalStatus();
    }
    private static String thermalName(int status) {
        switch(status) {
            case PowerManager.THERMAL_STATUS_NONE:return "NONE";
            case PowerManager.THERMAL_STATUS_LIGHT:return "LIGHT";
            case PowerManager.THERMAL_STATUS_MODERATE:return "MODERATE";
            case PowerManager.THERMAL_STATUS_SEVERE:return "SEVERE";
            case PowerManager.THERMAL_STATUS_CRITICAL:return "CRITICAL";
            case PowerManager.THERMAL_STATUS_EMERGENCY:return "EMERGENCY";
            case PowerManager.THERMAL_STATUS_SHUTDOWN:return "SHUTDOWN";
            default:return "UNKNOWN_"+status;
        }
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
    private File diagnosticFile() { return new File(getFilesDir(),"pipa-diagnostic.txt"); }
    private synchronized void logDiagnostic(String event) {
        String line=java.time.Instant.now().toString()+" "+event+"\n";
        try(FileOutputStream out=new FileOutputStream(diagnosticFile(),true)) {
            out.write(line.getBytes(StandardCharsets.UTF_8));
            out.getFD().sync();
        } catch(Exception ignored) { }
    }
    private void nativeDiagnostic(String stage) { logDiagnostic(stage); }
    private String readDiagnostic() {
        try {
            byte[] bytes=java.nio.file.Files.readAllBytes(diagnosticFile().toPath());
            return new String(bytes,StandardCharsets.UTF_8);
        } catch(Exception ignored) {
            return status==null?"Sem diagnóstico gravado.":status.getText().toString();
        }
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
        stressHold144.setEnabled(enabled && validSurface);
        stressFg144.setEnabled(enabled && validSurface);
        scene3dHold.setEnabled(enabled && validSurface);
        scene3dFg.setEnabled(enabled && validSurface);
        scene3dHold60.setEnabled(enabled && validSurface);
        scene3dFg60.setEnabled(enabled && validSurface);
        if(syncDisplay!=null)syncDisplay.setEnabled(enabled && validSurface);
        if(fastMotion!=null)fastMotion.setEnabled(enabled && validSurface);
        if(identity3d!=null)identity3d.setEnabled(enabled && validSurface);
        if(gpuBudgetGuard!=null)gpuBudgetGuard.setEnabled(enabled && validSurface);
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
        start(hz,continuous,holdInsteadOfFG,diagnostic,v2,false);
    }
    private void start(int hz,boolean continuous,boolean holdInsteadOfFG,boolean diagnostic,
                       boolean v2,boolean stress) {
        start(hz,continuous,holdInsteadOfFG,diagnostic,v2,stress,false);
    }
    private void start(int hz,boolean continuous,boolean holdInsteadOfFG,boolean diagnostic,
                       boolean v2,boolean stress,boolean scene3d) {
        start(hz,continuous,holdInsteadOfFG,diagnostic,v2,stress,scene3d,stress?1440:240);
    }
    private void start(int hz,boolean continuous,boolean holdInsteadOfFG,boolean diagnostic,
                       boolean v2,boolean stress,boolean scene3d,int requestedFrames) {
        if(!validSurface || !running.compareAndSet(false,true))return;
        toggle(false);
        final boolean alignWithDisplay=syncDisplay.isChecked();
        final int motionRadius=fastMotion.isChecked()?3:4;
        final boolean preferIdentity3d=scene3d && identity3d.isChecked();
        final boolean adaptiveGuard=scene3d && continuous && !holdInsteadOfFG &&
                                    gpuBudgetGuard.isChecked();
        final int thermalStart=currentThermalStatus();
        peakThermalStatus.set(thermalStart);
        logDiagnostic("RUN_START hz="+hz+" continuous="+continuous+" hold="+
            holdInsteadOfFG+" stress="+stress+" scene3d="+scene3d+" sync="+
            alignWithDisplay+" guard="+adaptiveGuard+" frames="+requestedFrames);
        status.setText("MOTION raio="+motionRadius+" "+
              (scene3d?(preferIdentity3d?"WSI IDENTITY ":"WSI CURRENT "):"")+
              (adaptiveGuard?"GPU GUARD PAR 85% ":"GPU FIXO ")+
              (alignWithDisplay?"SYNC WSI ":"FIXED 144 ")+
              (requestedFrames>=8640?"TESTE 60s ":stress?"TESTE 10s ":"TESTE CURTO ")+
              (scene3d?"CENA 3D ":v2?"CENA V2 ":diagnostic?"CENA DIAG ":"CENA ORIGINAL ")+
              (holdInsteadOfFG?"HOLD GPU ":continuous?"2x GPU ":"A/B ")+hz+
              " Hz | tela "+displayHz()+" Hz | criando Vulkan...");
        final Surface surface=surfaceView.getHolder().getSurface();
        new Thread(()->{
            String result;
            try {
                byte[] motion=load("pipa_motion_sparse.comp.spv");
                byte[] warp=load("pipa_interpolate_tiled.comp.spv");
                byte[] scene=continuous?load(scene3d?"pipa_scene_3d.comp.spv":
                    v2?"pipa_scene_v2.comp.spv":
                    diagnostic?"pipa_scene_diagnostic.comp.spv":"pipa_scene.comp.spv"):null;
                result=nativePresent(surface,motion,warp,scene,hz,requestedFrames,
                                     continuous,holdInsteadOfFG,alignWithDisplay,motionRadius,
                                     scene3d,preferIdentity3d,adaptiveGuard);
            } catch(Throwable ex) {
                result="Falha: "+ex.getClass().getSimpleName()+": "+ex.getMessage();
                logDiagnostic("RUN_EXCEPTION "+result);
            }
            final int thermalEnd=currentThermalStatus();
            peakThermalStatus.accumulateAndGet(thermalEnd,Math::max);
            final int thermalPeak=peakThermalStatus.get();
            logDiagnostic("RUN_END "+result);
            final String finalResult=result+(scene3d?
                " | FONTE=3D raycast perspectiva e oclusao":
                v2?
                " | FONTE=V2 tileable sem clamp":
                diagnostic?" | FONTE=DIAGNOSTICA quadrantes solidos; sem ruido":
                " | FONTE=PROCEDURAL antiga")+
                " | alvo="+(requestedFrames/hz)+"s presentsSolicitados="+requestedFrames+
                " | thermal Android início="+thermalName(thermalStart)+
                " pico="+thermalName(thermalPeak)+" fim="+thermalName(thermalEnd);
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
        logDiagnostic("SURFACE_DESTROYED running="+running.get());
        validSurface=false;
        nativeStop();
        toggle(false);
    }
    @Override protected void onDestroy() {
        logDiagnostic("ACTIVITY_DESTROY changingConfig="+isChangingConfigurations()+
            " finishing="+isFinishing()+" running="+running.get());
        if(powerManager!=null)powerManager.removeThermalStatusListener(thermalStatusListener);
        nativeStop();
        super.onDestroy();
    }
    @Override protected void onPause() {
        logDiagnostic("ACTIVITY_PAUSE running="+running.get());
        super.onPause();
    }
    @Override protected void onStop() {
        logDiagnostic("ACTIVITY_STOP running="+running.get());
        super.onStop();
    }
}
