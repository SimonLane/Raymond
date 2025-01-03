#include "CRC.h"
#define ETL Serial1
#include <SPI.h>

//~~~~~~~~~~~~~~~~~~~~~~~~~~ETL functions ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

int ETL_offset = 0;     //in microns
int ETL_position = 0;   //in microns

void ETL_handshake(){
  int incomingByte;
  ETL_clear_buffer();
  Serial.print("to ETL: Start --> ");
  ETL.print("Start");
  delay(10);
  while (ETL.available() > 0) {
    incomingByte = ETL.read();
    Serial.write(incomingByte);
  }
  Serial.write("\r");
  //Set ETL temperature limits 
  ETL.write(0x50);ETL.write(0x77);ETL.write(0x54);ETL.write(0x41);ETL.write(0x02);ETL.write(0x30);
  ETL.write(0x01);ETL.write(0x40);ETL.write(0x32);ETL.write(0x37);
//set ETL Focal power mode  
  ETL.write(0x4d);ETL.write(0x77);ETL.write(0x43);ETL.write(0x41);ETL.write(0x56);ETL.write(0x76);

  //Todo - put into analog mode
  ETL.write(0x4d); // M, mode
  ETL.write(0x77); // w, write
  ETL.write(0x41); // A, analog
  ETL.write(0x41); // A, channel A
  uint16_t CS = crc16(0x4d774141, 8, 0x8005, 0, 0, true, true); //only use the first 8 bytes 
  ETL.write(CS & 0xFF); // CRC byte1
  ETL.write(CS>>8); // CRC byte2
}

void ETL_clear_buffer(){while (ETL.available() > 0) {ETL.read();}}

float ETL_Temp(){
  int incomingByte;
  ETL_clear_buffer();
  ETL.print("T");ETL.print("A");ETL.write(0xFE);ETL.write(0xF0);
  int b = 0;
  int t = 0;
  delay(10);
  while (ETL.available() > 0) {
      incomingByte = ETL.read();
      if(b==3){t = t | (incomingByte<<8);}
      if(b==4){t = t | incomingByte;}
      b++;
    }
  return (t * 0.0625);
}


void ETLto(int p){
  ETL_position = p;
  p = p + ETL_offset;

// new way via analog
  


  //old way, does not work on 16mm lens
////fp range is 700 to 1700 (-1.5 to 3.5 diopters)
//  
//  if(p<700 || p>1700){return false;} //out of range check
////template command structure, 10 bytes:
//  //  P       w       C         A         FH FL   0   0   CS1  CS2
//  // "Power"  write   Control   Channel   focus   dummy   checksum
//  char focus_output_[10] = {0x50,0x77,0x44,0x41,0x00,0x00,0x00,0x00,0x00,0x00}; 
////add focus bytes
//  focus_output_[4] = p >> 8;
//  focus_output_[5] = p & 0xFF;
////generate checksum
//  uint16_t CS = crc16(focus_output_, 8, 0x8005, 0, 0, true, true); //only use the first 8 bytes
//  focus_output_[8] = CS & 0xFF;   //break CS into two bytes, and reverse the order
//  focus_output_[9] = CS>>8; 
////write the binary data to the ETL
//  for(int i;i<10;i++){ETL.write(focus_output_[i]);}
}

void ETLoffset(int OS){
  ETL_offset = OS;
  ETLto(ETL_position);
}

//~~~~~~~~~~~~~~~~~~~~~~~~~~ LED functions ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
int LED_status = 0;
int LEDpin = 20;

void LEDon(){
  digitalWrite(20, HIGH);
  hablar("LED on");
  LED_status = 1;
}

void LEDoff(){
  digitalWrite(20, LOW);
  hablar("LED off");
  LED_status = 0;
}

//~~~~~~~~~~~~~~~~~~~~~~~~~~ mirror functions ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

const int slaveSelectPin = 10;
const int DNreadyPin = 35;
int TriggerPin = 34;


uint32_t generateSPFPR(float f) {
  float normalized;
  int16_t shift;
  int32_t sign, exponent, significand;
 
  if (f == 0.0){return 0;} //handle this special case
                          //check sign and begin normalization
  if (f < 0) { sign = 1; normalized = -f; } 
  else { sign = 0; normalized = f; }
                          //get normalized form of f and track the exponent
  shift = 0;
  while (normalized >= 2.0) { normalized /= 2.0; shift++; }
  while (normalized < 1.0)  { normalized *= 2.0; shift--; }
  normalized = normalized - 1.0;
                          //calculate binary form (non-float) of significand 
  significand = normalized*(0x800000 + 0.5f);
                          //get biased exponent
  exponent = shift + 0x7f; //shift + bias
                          //combine and return
  return (sign<<31) | (exponent<<23) | significand;
}

void sendWriteSPI(uint32_t registers, uint32_t valueX, uint32_t valueY){   // quick function to write 'standard' format commands to the mirror

  while(digitalRead(DNreadyPin) == HIGH){}                         //wait for slave to be ready
  SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE1));
  digitalWrite(slaveSelectPin,LOW);
                           SPI.transfer(0x00);SPI.transfer(0x01);       //write command
  for(int i=24;i>-8;i=i-8){SPI.transfer((registers >> i) & 0xFF);}      //registers
  for(int i=24;i>-8;i=i-8){SPI.transfer((valueX >> i) & 0xFF);}         //X command
  for(int i=24;i>-8;i=i-8){SPI.transfer((valueY >> i) & 0xFF);}         //Y command
  digitalWrite(slaveSelectPin,HIGH);
  SPI.endTransaction();
  
}

void mirrorGain(int gY, int gZ){
  //gains received as ints for convenience of sending over serial protocol
  //convert to floats and invert, as gains required are always < 1
  sendWriteSPI(0x98009900,generateSPFPR(float(1.0/gY)),generateSPFPR(float(1.0/gZ)));
}

void mirrorOffset(int osY, int osZ){
  sendWriteSPI(0x98019901,generateSPFPR(float(osY)),generateSPFPR(float(osZ)));
}


void mirrorTo(int pY, int pZ){
  
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
    if(device == "hello")                         {Serial.println("Hi there!");}

// Illumination controls    
    if(device == "LEDon")                         {LEDon();}
    if(device == "LEDoff")                        {LEDoff();}

// ETL controls
    if(device == "ETLoffset")                     {ETLoffset(command1.toInt());hablar("ETL offset");}
    if(device == "ETLto")                         {ETLto(command1.toInt());hablar("ETL move");}
  
// mirror controls - to do
    if(device == "Yto")                           {}
    if(device == "Zto")                           {}
    if(device == "Yoffset")                       {}
    if(device == "Zoffset")                       {}
    if(device == "Ygain")                         {}
    if(device == "Zgain")                         {}
   
}

//  ~~~~~~~~~~~~~~~~~~~~~~~~~~ setup ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
void setup() {
  Serial.begin(115200);
  pinMode(20,OUTPUT);
  pinMode(A21,OUTPUT);
  analogWriteResolution(12);
  ETL.begin(38400); 
  delay(100);
  ETL_handshake();//put ETL into analog mode
  //mirror_handshake(); //TO DO 

}

//~~~~~~~~~~~~~~~~~~~~~~~~~~ main loop ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


long unsigned prev_t = 0;
int k=700;
int inc = 1;


void loop() {
checkSerial();
//if(millis() > prev_t + 1){
//  prev_t = millis();
//  ETLto(k);
//  k = k + inc;
//  if(k > 1700)  {inc = inc * -1.0;}
//  if(k < 700)   {inc = inc * -1.0;}
//  }

}
