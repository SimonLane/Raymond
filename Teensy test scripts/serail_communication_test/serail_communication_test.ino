void setup() {
  Serial.begin(115200);
  delay(1000);
}

void loop() {
  checkSerial(); 
}

//~~~~~~~~~~~~~~~~~~~~~~~~~~ Serial communications ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
String device = "";
String command1 = "";
String command2 = "";
int serial_part = 0;
bool Verbose = true;

void checkSerial(){
  char rc;
  while (Serial.available()) {
   rc = Serial.read();
   if (rc == 47)      {serial_part = 1; device = "";command1 = "";command2 = "";}  // '/' char
   else if (rc == 46)      {serial_part += 1;}                                     // '.' char
   else if (rc == 59)      {respond(device,command1,command2); serial_part = 0;}   // ';' char
   else if (serial_part == 1){device   += rc;}
   else if (serial_part == 2){command1 += rc;}
   else if (serial_part == 3){command2 += rc;}
 }
}

void hablar(String parabla){
  if(Verbose == true){Serial.println(parabla);}
}

void respond(String device,String command1, String command2) {
  hablar("Serial in: " + device + '.' + command1 + '.' + command2);
    if(device == "hello")                     {Serial.println("laser controller");}
                                          
}
