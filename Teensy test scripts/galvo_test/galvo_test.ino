//Test script for Scan Engine v3 board, using the Analog output (21,22) on Teensy 3.5 to control Galvo mirrors
// via dual ouput amplifier circuit

void setup() {
  Serial.begin(115200);           
  analogWriteResolution(12);
  pinMode(A21,OUTPUT);
  pinMode(14,OUTPUT);
  analogWrite(A22,2047);
  analogWrite(A21,2047);
  digitalWrite(14,1);
}

int galvo = A22;

// serial commands
String device = "";
String command1 = "";
String command2 = "";
String command3 = "";
int serial_part = 0;
bool scan_mode = false;
int g = A22;

void checkSerial() {   
  char rc;
  while (Serial.available()) {
   rc = Serial.read();
   if (rc == 47)      {serial_part = 1; device = "";command1 = "";command2 = "";}  // '/' char
   else if (rc == 46)      {serial_part += 1;}                                     // '.' char
   else if (rc == 59)      {respond(device,command1,command2); serial_part = 0;}   // ';' char
   else if (serial_part == 1){device   += rc;}
   else if (serial_part == 2){command1 += rc;}
   else if (serial_part == 3){command2 += rc;}
   else if (serial_part == 4){command3 += rc;}
 }
}

void respond(String device,String command1, String command2) {
  if(device == "hello")       {Serial.println("Hi there!");}
//galvo_calibration
    if(device == "a0")        {analogWrite(A22,0);Serial.println("A0");}
    if(device == "a1")        {analogWrite(A22,1023);Serial.println("A1023");}
    if(device == "a2")        {analogWrite(A22,2047);Serial.println("A2047");}
    if(device == "a3")        {analogWrite(A22,3071);Serial.println("A3071");}
    if(device == "a4")        {analogWrite(A22,4095);Serial.println("A4095");}

    if(device == "b0")        {analogWrite(A21,0);Serial.println("B0");}
    if(device == "b1")        {analogWrite(A21,1023);Serial.println("B1023");}
    if(device == "b2")        {analogWrite(A21,2047);Serial.println("B2047");}
    if(device == "b3")        {analogWrite(A21,3071);Serial.println("B3071");}
    if(device == "b4")        {analogWrite(A21,4095);Serial.println("B4095");}

    if(device == "A")         {analogWrite(A22,command1.toInt());Serial.print("A");Serial.println(command1);}
    if(device == "SA")        {scan_mode = true; scan_galvo(A22);Serial.println("Scanning A");}
    if(device == "SB")        {scan_mode = true; scan_galvo(A21);Serial.println("Scanning B");}
    if(device == "ES")        {scan_mode = false;Serial.println("End Scan");}
    
    command1= "";command2= "";command3= "";
  }

  void scan_galvo(int galvo){
    g=galvo;
}
void loop() {
  checkSerial();
  if(scan_mode==true){
    for(int i = 0;i<360;i++){
      
      analogWrite(A22,(sin(i*(3.14/180.0))*250)+2048);
      analogWrite(A21,(sin((i+90)*(3.14/180.0))*250)+2048);
      delay(10);

    }
    Serial.print(".");
  }
  
}
