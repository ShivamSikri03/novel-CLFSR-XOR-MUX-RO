module FIRO_main (
    input enable,
    (*DONT_TOUCH = "TRUE"*) output wire out
);
`ifndef SYNTHESIS
    (*DONT_TOUCH = "TRUE"*) wire w1,w2,w3,w4;
    integer d1=1,d2=1,d3=1,d4=1;

    always begin
        #3;
        d1 = 1 + ({$urandom} % 3);
        d2 = 1 + ({$urandom} % 3);
        d3 = 1 + ({$urandom} % 3);
        d4 = 1 + ({$urandom} % 3);
    end

    assign #(d1) w1 = ~(w4 & enable);
    assign #(d2) w2 = ~w1;
    assign #(d3) w3 = ~w2;
    assign #(d4) w4 = w1^w2^w3;
    assign out = w3;

    initial begin
        force w3 = 1'b0;
        #10; 
        release w3;
    end
`else
(*DONT_TOUCH = "TRUE"*) wire w1,w2,w3,w4;
assign w1 = ~(w4 & enable);
assign w2 = ~w1;
assign w3 = ~w2;
assign w4 = w1^w2^w3;
assign out = w3; 
`endif

endmodule

