#include "CRC.h"
#define ETL Serial1

void setup() {

  attachInterrupt(digitalPinToInterrupt(2), ETLtrigger, CHANGE);
  
  Serial.begin(115200);
  ETL.begin(38400); 

  pinMode(20, OUTPUT);
  pinMode(2, INPUT);
  delay(1000);
  handshake();

//Set temperature limits 
  ETL.write(0x50);ETL.write(0x77);ETL.write(0x54);ETL.write(0x41);ETL.write(0x02);ETL.write(0x30);
  ETL.write(0x01);ETL.write(0x40);ETL.write(0x32);ETL.write(0x37);
//set Focal power mode  
  ETL.write(0x4d);ETL.write(0x77);ETL.write(0x43);ETL.write(0x41);ETL.write(0x56);ETL.write(0x76);
}
void ETLtrigger(){
  Serial.print("trigger: ");
  Serial.println(digitalRead(2));
}


int incomingByte;

void handshake(){
  clear_buffer();
  Serial.print("to ETL: Start --> ");
  ETL.print("Start");
  delay(10);
  while (ETL.available() > 0) {
    incomingByte = ETL.read();
    Serial.write(incomingByte);
  }
  Serial.write("\r");
}

void clear_buffer(){while (ETL.available() > 0) {ETL.read();}}


float Temp(){
  clear_buffer();
  ETL.print("T");
  ETL.print("A");
  ETL.write(0xFE);
  ETL.write(0xF0);
  int b = 0;
  int t = 0;
  delay(10);
  while (ETL.available() > 0) {
      incomingByte = ETL.read();
      if(b==3){t = t | (incomingByte<<8);}
      if(b==4){t = t | incomingByte;}
      b++;
    }
  Serial.println(t * 0.0625);
}


void focus(float f){
  clear_buffer();
//f is in diopters, convert to focal position
//fp 'focal point' is the (diopters + 5) * 200
//diopter range is -1.5 to +3.5, fp range is 700 to 1700

  int fp = round((f + 5.0) * 200.0);
  
  //Serial.print("set focus: ");Serial.print(f);Serial.print(" diopters, (");Serial.print(fp);Serial.println(" units)");
  if(fp<700 || fp>1700){return false;} //out of range check
//template  
//command structure, 10 bytes:
  //  P    w     [Sinusoidal]    A      FH FL   0   0   CS1  CS2
  // "P"  write   S/Q/D/T/C   Channel   focus   dummy   checksum
  char focus_output_[10] = {0x50,0x77,0x44,0x41,0x00,0x00,0x00,0x00,0x00,0x00}; 
//add focus bytes
  focus_output_[4] = fp >> 8;
  focus_output_[5] = fp & 0xFF;
//generate checksum
  uint16_t CS = crc16(focus_output_, 8, 0x8005, 0, 0, true, true); //only use the first 8 bytes
  focus_output_[8] = CS & 0xFF;   //break CS into two bytes, and reverse the order
  focus_output_[9] = CS>>8; 
//write the binary data to the ETL
  for(int i;i<10;i++){ETL.write(focus_output_[i]);}
}

void focus(int fp){
  clear_buffer();
//fp range is 700 to 1700

  //Serial.print("set focus: ");Serial.print(fp);Serial.println(" units");
  if(fp<700 || fp>1700){return false;} //out of range check
//template  
//command structure, 10 bytes:
  //  P    w     [Sinusoidal]    A      FH FL   0   0   CS1  CS2
  // "P"  write   S/Q/D/T/C   Channel   focus   dummy   checksum
  char focus_output_[10] = {0x50,0x77,0x44,0x41,0x00,0x00,0x00,0x00,0x00,0x00}; 
//add focus bytes
  focus_output_[4] = fp >> 8;
  focus_output_[5] = fp & 0xFF;
//generate checksum
  uint16_t CS = crc16(focus_output_, 8, 0x8005, 0, 0, true, true); //only use the first 8 bytes
  focus_output_[8] = CS & 0xFF;   //break CS into two bytes, and reverse the order
  focus_output_[9] = CS>>8; 
//write the binary data to the ETL
  for(int i;i<10;i++){ETL.write(focus_output_[i]);}
}

long unsigned prev_t = 0;
long unsigned prev_temp = 0;
int k=700;
int inc = 10;


void loop() {

if(millis() > prev_t + 5){
  prev_t = millis();
  focus(k);
  k = k + inc;
  if(k > 1700)  {inc = inc * -1;}
  if(k < 700)   {inc = inc * -1;}
  }
  
if(millis() > prev_temp + 1000){
  prev_temp = millis();
  Temp();

  
  }
}
