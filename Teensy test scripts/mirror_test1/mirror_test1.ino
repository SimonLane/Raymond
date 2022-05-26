#include "CRC.h"
#include <SPI.h>

const int   SlaveSelectPin = 10;
const int   DNreadyPin = 35;
int         MirrorTrigger = 34;
int         CameraTrigger = 25;


void setup() {
  pinMode (SlaveSelectPin, OUTPUT);
  pinMode (MirrorTrigger, OUTPUT);
  pinMode (CameraTrigger, OUTPUT);
  pinMode (13, OUTPUT);
  pinMode (DNreadyPin, INPUT);
  digitalWrite (SlaveSelectPin, HIGH);
  SPI.begin(); 
  Serial.begin(9600);
  delay(1000);
  //mirrorSetup();
}

void loop() {
  //call the trigger pin once per second
//  digitalWrite(MirrorTrigger,0);
//  delay(1);
//  digitalWrite(MirrorTrigger,0);
//  delay(3000);
  
  digitalWrite(CameraTrigger,1);
  delay(500);
  digitalWrite(CameraTrigger,0);
  delay(500);
  
}


void mirrorSetup(){
  //sendWriteSPI(0x40004005,0x60,0x61);       //Select signal generator system as active input for X and Y axis.
  
  sendWriteSPI(0x40024007,0xc0,0xc1); //activate closed loop control
  sendWriteSPI(0x98009900,generateSPFPR(0.01),generateSPFPR(0.01));       //Set the Gains
  sendWriteSPI(0x98019901,generateSPFPR(0.0065),generateSPFPR(-0.0066));  //Set the Offsets
  sendWriteSPI(0x50025102,generateSPFPR(-0.8),generateSPFPR(0.0));         //set static position

//set signal generation (on axis 0)
  sendWriteSPI(0x40004000,0x60,0x61);       //Select signal generator system as active input for X axis.  

  sendWriteSPI(0x60006007,0x02,0xFFFF);         //set unit type (02:XY 01:O; 00:current), set cycles
  sendWriteSPI(0x60026003,0x04,generateSPFPR(1));  //waveform (0:sine 1:Triangle 2:Square 3:Sawtooth 4:Pulse), Frequency
  sendWriteSPI(0x60046005,generateSPFPR(1),generateSPFPR(0));  //Amplitude, Offset
  sendWriteSPI(0x60096001,0x01,0x01);  //trigger, Run Flag
  

}

void sendWriteSPI(uint32_t registers, uint32_t valueA, uint32_t valueB){   // quick function to write 'standard' format commands to the mirror

  while(digitalRead(DNreadyPin) == HIGH){}                         //wait for slave to be ready
  SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE1));
  digitalWrite(SlaveSelectPin,LOW);
                           SPI.transfer(0x00);
                           //Serial.println(0x00,HEX);
                           SPI.transfer(0x01);
                           //Serial.println(0x01,HEX);       //write command
  for(int i=24;i>-8;i=i-8){SPI.transfer((registers >> i) & 0xFF);
  //Serial.println((registers >> i) & 0xFF,HEX);
  }      //registers
  for(int i=24;i>-8;i=i-8){SPI.transfer((valueA >> i) & 0xFF);
  //Serial.println((valueA >> i) & 0xFF,HEX);
  }         //X command
  for(int i=24;i>-8;i=i-8){SPI.transfer((valueB >> i) & 0xFF);
  //Serial.println((valueB >> i) & 0xFF,HEX);
  }         //Y command
  digitalWrite(SlaveSelectPin,HIGH);
  SPI.endTransaction();
}

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
