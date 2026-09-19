package com.phonease;
import org.junit.jupiter.api.Test;
import org.springframework.util.LinkedMultiValueMap;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.util.Base64;
import static org.junit.jupiter.api.Assertions.*;

class TelephoneTests {
    @Test void signedCanonicalUrlAndRepeatedFormValues() throws Exception {
        var form=new LinkedMultiValueMap<String,String>();
        form.add("SpeechResult","yes"); form.add("CallSid","CA123"); form.add("SpeechResult","yes");
        String url="https://phonease.example/twilio/turn?sid=test&revision=2";
        Mac mac=Mac.getInstance("HmacSHA1"); mac.init(new SecretKeySpec("secret".getBytes(),"HmacSHA1"));
        String signature=Base64.getEncoder().encodeToString(mac.doFinal((url+"CallSidCA123SpeechResultyes").getBytes()));
        assertTrue(TelephoneController.signatureValid(url,form,signature,"secret"));
        assertFalse(TelephoneController.signatureValid(url+"3",form,signature,"secret"));
        assertFalse(TelephoneController.signatureValid(url,form,signature,""));
        form.set("SpeechResult","no");
        assertFalse(TelephoneController.signatureValid(url,form,signature,"secret"));
    }
}
